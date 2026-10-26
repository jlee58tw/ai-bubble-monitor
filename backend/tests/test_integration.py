"""End-to-end: recorded EDGAR fixtures -> provider (mock HTTP) -> DB -> derived -> API."""
import datetime as dt
import json

import httpx
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from tests.conftest import FIX


def mock_client_factory(calls):
    docs = {"0000789019": json.loads((FIX / "companyfacts_msft.json").read_text()),
            "0001018724": json.loads((FIX / "companyfacts_amzn.json").read_text())}

    def handler(request: httpx.Request):
        calls.append(request)
        assert request.headers["User-Agent"] == "AIBM test test@example.com"
        cik = request.url.path.split("CIK")[1].split(".")[0]
        if cik in docs:
            return httpx.Response(200, json=docs[cik])
        return httpx.Response(404, text="not in fixture")

    return lambda: httpx.Client(transport=httpx.MockTransport(handler),
                                headers={"User-Agent": "AIBM test test@example.com"})


def test_end_to_end(db_session, monkeypatch):
    from app.models import IngestionError, Observation
    from app.providers.sec_edgar import SecEdgarProvider
    from app.services.ingest import run_ingestion

    calls = []
    prov = SecEdgarProvider(user_agent="AIBM test test@example.com", max_rps=10,
                            client_factory=mock_client_factory(calls))
    runs = run_ingestion(db_session, ["sec_edgar"], trigger="test",
                         entity_ids=["MSFT", "AMZN", "META"], providers={"sec_edgar": prov})
    assert runs[0].status == "partial"           # META not in fixture -> logged error, not silent
    assert runs[0].records_inserted > 0
    errs = db_session.scalars(select(IngestionError)).all()
    assert any(e.entity_id == "META" for e in errs)
    assert runs[1].provider == "derived" and runs[1].status == "success"
    assert len(calls) == 3

    # idempotent: second run inserts nothing new
    runs2 = run_ingestion(db_session, ["sec_edgar"], trigger="test", entity_ids=["MSFT", "AMZN"],
                          providers={"sec_edgar": prov})
    assert runs2[0].records_inserted == 0 and runs2[0].records_revised == 0
    assert runs2[1].records_inserted == 0

    # derived values
    def cur(metric, ent, end):
        from app.services.queries import query_observations
        rows = query_observations(db_session, [metric], [ent], start=end, end=end)
        assert len(rows) == 1, (metric, ent, end, rows)
        return rows[0]

    capex = cur("capex_total", "MSFT", dt.date(2025, 6, 30))
    ocf = cur("operating_cash_flow", "MSFT", dt.date(2025, 6, 30))
    fcf = cur("fcf", "MSFT", dt.date(2025, 6, 30))
    assert fcf.value == ocf.value - capex.value and fcf.classification == "derived"
    assert cur("capex_to_ocf", "MSFT", dt.date(2025, 6, 30)).value == capex.value / ocf.value
    y = cur("capex_yoy", "AMZN", dt.date(2026, 6, 30))
    assert abs(y.value - (54_208 / 32_183 - 1)) < 1e-9

    # API
    from app.main import app
    with TestClient(app) as c:
        r = c.get("/api/observations", params={"metric_id": "capex_total", "entity_id": "AMZN"})
        assert r.status_code == 200 and len(r.json()) > 4
        row = r.json()[-1]
        for f in ("publication_date", "source_url", "classification", "confidence", "fiscal_period"):
            assert row[f] is not None
        # point-in-time: as of 2026-05-01 the Q2-2026 value did not exist yet
        r = c.get("/api/observations", params={"metric_id": "capex_total", "entity_id": "AMZN",
                                               "as_of": "2026-05-01"})
        assert max(x["period_end"] for x in r.json()) == "2026-03-31"
        r = c.get("/api/observations.csv", params={"metric_id": "fcf", "entity_id": "MSFT"})
        assert r.status_code == 200 and r.text.splitlines()[0].startswith("id,metric_id")
        st = c.get("/api/ingestion/status").json()
        states = {(s["metric_id"], s["entity_id"]): s["state"] for s in st["series"]}
        assert states[("capex_total", "META")] == "missing"          # missing is flagged, not zero
        assert states[("nvda_datacenter_revenue", "NVDA")] == "unavailable"
        cards = c.get("/api/overview").json()["cards"]
        meta = [x for x in cards if x["metric_id"] == "capex_total" and x["entity_id"] == "META"][0]
        assert meta["status"] == "missing" and meta["current"] is None
        assert len(c.get("/api/metrics").json()) >= 10


def test_revision_is_appended_not_overwritten(db_session):
    from app.models import IngestionRun, Observation
    from app.providers.base import ObservationRecord
    from app.registry.registry import sync_registry
    from app.services.ingest import store_records
    from app.services.queries import query_observations

    sync_registry(db_session)
    run = IngestionRun(provider="test", trigger="test", status="running"); db_session.add(run); db_session.flush()
    base = dict(metric_id="capex_total", entity_id="META", unit="USD", period_start=dt.date(2024, 1, 1),
                period_end=dt.date(2024, 3, 31), source_type="sec_edgar_xbrl", classification="reported",
                confidence="high")
    c1 = store_records(db_session, run, [ObservationRecord(value=10.0, publication_date=dt.date(2024, 5, 1), **base)])
    c2 = store_records(db_session, run, [ObservationRecord(value=11.0, publication_date=dt.date(2025, 5, 1), **base)])
    assert c1["inserted"] == 1 and c2["revised"] == 1
    rows = db_session.scalars(select(Observation).order_by(Observation.version)).all()
    assert [(r.value, r.version) for r in rows] == [(10.0, 1), (11.0, 2)]
    assert rows[1].supersedes_id == rows[0].id
    assert [o.value for o in query_observations(db_session, ["capex_total"])] == [11.0]
    assert [o.value for o in query_observations(db_session, ["capex_total"], as_of=dt.date(2024, 12, 31))] == [10.0]
    assert len(query_observations(db_session, ["capex_total"], include_history=True)) == 2
