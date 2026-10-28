"""Leak check: reports only counts/booleans, never the secret itself."""
import os, subprocess, sys
sys.path.insert(0, os.path.dirname(__file__))
from common import settings, ROOT
tok = settings().tiingo_api_key or ""
print("token_configured:", bool(tok))
if not tok:
    sys.exit(0)
files = subprocess.run(["git", "ls-files", "-co", "--exclude-standard"], cwd=ROOT, capture_output=True, text=True).stdout.split()
paths = [os.path.join(ROOT, f) for f in files] + [p for p in ["/tmp/aibm_api.log", "/tmp/aibm_web.log"] if os.path.exists(p)]
hits = 0
for p in paths:
    try:
        if tok in open(p, errors="ignore").read():
            hits += 1
    except (IsADirectoryError, FileNotFoundError):
        pass
diff = subprocess.run(["git", "diff", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout
print("files_scanned:", len(paths), "files_with_token:", hits, "token_in_diff:", tok in diff)
env_tracked = subprocess.run(["git", "ls-files", "backend/.env"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
print("backend/.env tracked:", bool(env_tracked))
