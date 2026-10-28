"""Shared helpers for the independent data audit (scripts/audit). Deliberately does NOT import app.providers
or app.services: sources are fetched fresh with urllib and compared to stored rows read via plain SQL."""
import datetime as dt, json, os, sqlite3, sys, time, urllib.request, gzip

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT = os.path.join(ROOT, "docs", "verification")
os.makedirs(OUT, exist_ok=True)


def db():
    sys.path.insert(0, os.path.join(ROOT, "backend"))
    url = settings().database_url
    path = url.split("sqlite:///", 1)[1]
    if not os.path.isabs(path):
        path = os.path.join(ROOT, "backend", path)
    return sqlite3.connect(path)


def settings():
    sys.path.insert(0, os.path.join(ROOT, "backend"))
    cwd = os.getcwd(); os.chdir(os.path.join(ROOT, "backend"))      # .env is read relative to backend/
    try:
        from app.config import get_settings
        return get_settings()
    finally:
        os.chdir(cwd)


def sec_headers():
    ua = settings().sec_user_agent
    assert ua, "SEC_USER_AGENT not configured"
    return {"User-Agent": ua}


_last = [0.0]


def fetch(url, headers=None, min_gap=0.25, raw=False):
    gap = time.time() - _last[0]
    if gap < min_gap:
        time.sleep(min_gap - gap)
    h = {"User-Agent": "Mozilla/5.0 (research audit)"}
    h.update(headers or {})
    import subprocess
    cmd = ["curl", "-sS", "--compressed", "-L", "--max-time", "90", "-w", "\n%{http_code}"]
    for k, v in h.items():
        cmd += ["-H", f"{k}: {v}"]
    out = subprocess.run(cmd + [url], capture_output=True).stdout
    body, _, code = out.rpartition(b"\n")
    if code.strip() != b"200":
        raise RuntimeError(f"HTTP {code.decode().strip()} for {url}")
    b = body
    _last[0] = time.time()
    return b if raw else b.decode("utf-8", "replace")


def latest_rows(con, metric, entity=None, since=None):
    q = ("select id, entity_id, fiscal_period, period_start, period_end, publication_date, value, classification, "
         "source_url, methodology from observations o where metric_id=? "
         "and not exists (select 1 from observations n where n.supersedes_id=o.id)")
    a = [metric]
    if entity:
        q += " and entity_id=?"; a.append(entity)
    if since:
        q += " and period_end>=?"; a.append(since)
    return con.execute(q + " order by entity_id, period_end", a).fetchall()


class Results:
    def __init__(self, family):
        self.family, self.rows = family, []

    def add(self, check, stored, source, ok, url, note=""):
        self.rows.append(dict(check=check, stored=stored, source=source, ok=bool(ok) if ok is not None else None,
                              url=url, note=note))
        flag = "PASS" if ok else ("N/A" if ok is None else "FAIL")
        print(f"[{flag}] {check}: stored={stored} source={source} {note}")

    def save(self):
        with open(os.path.join(OUT, f"{self.family}.json"), "w") as f:
            json.dump(dict(family=self.family, checked_at=dt.datetime.now().astimezone().isoformat(timespec="seconds"),
                           rows=self.rows), f, indent=1, default=str)
        n = len(self.rows); p = sum(1 for r in self.rows if r["ok"]); fl = sum(1 for r in self.rows if r["ok"] is False)
        print(f"== {self.family}: {p} pass / {fl} fail / {n - p - fl} n/a")


def close(a, b, rel=1e-6, abs_=0.0):
    if a is None or b is None:
        return False
    return abs(a - b) <= max(abs_, rel * max(abs(a), abs(b)))
