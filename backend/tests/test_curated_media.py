import datetime as dt

import pytest
import yaml

from app.providers import curated_media as CM
from app.registry.registry import get_registry


def test_curated_file_valid_and_all_estimated():
    res = CM.CuratedMediaProvider().fetch(get_registry())
    assert res.errors == []
    assert len(res.records) == 7
    assert {r.classification for r in res.records} == {"estimated"}
    assert {r.confidence for r in res.records} == {"low"}
    assert all(r.source_url.startswith("https://") and "Verbatim:" in r.methodology for r in res.records)
    q2 = [r for r in res.records if r.entity_id == "OPENAI" and r.metric_id == "ai_lab_revenue_media"
          and r.period_end == dt.date(2026, 6, 30)]
    assert q2[0].value == 6.7e9 and q2[0].publication_date == dt.date(2026, 8, 18)


@pytest.mark.parametrize("patch,msg", [({"url": ""}, "missing"), ({"quote": None}, "missing"),
                                       ({"url": "http://x"}, "https"),
                                       ({"published": "2026-06-01"}, "look-ahead")])
def test_validation_rejects_bad_rows(tmp_path, patch, msg):
    good = {"metric": "ai_lab_revenue_media", "entity": "OPENAI", "period_start": "2026-04-01",
            "period_end": "2026-06-30", "value": 1, "published": "2026-08-18", "outlet": "X",
            "url": "https://example.com/a", "quote": "q"}
    f = tmp_path / "c.yaml"
    f.write_text(yaml.safe_dump({"items": [good | patch]}))
    res = CM.CuratedMediaProvider(f).fetch(get_registry())
    assert res.records == [] and msg in res.errors[0].message


def test_unregistered_metric_rejected(tmp_path):
    f = tmp_path / "c.yaml"
    f.write_text(yaml.safe_dump({"items": [{"metric": "revenue", "entity": "OPENAI", "period_start": "2026-01-01",
                                            "period_end": "2026-03-31", "value": 1, "published": "2026-05-01",
                                            "outlet": "X", "url": "https://e.com", "quote": "q"}]}))
    res = CM.CuratedMediaProvider(f).fetch(get_registry())
    assert res.records == [] and "not registered" in res.errors[0].message
