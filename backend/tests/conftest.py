import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("LOG_JSON", "false")
FIX = Path(__file__).parent / "fixtures"


@pytest.fixture
def msft_doc():
    return json.loads((FIX / "companyfacts_msft.json").read_text())


@pytest.fixture
def amzn_doc():
    return json.loads((FIX / "companyfacts_amzn.json").read_text())


@pytest.fixture
def db_session(tmp_path):
    from sqlalchemy.orm import sessionmaker

    from app.db import Base, make_engine, set_engine
    eng = make_engine(f"sqlite:///{tmp_path}/test.db")
    Base.metadata.create_all(eng)
    set_engine(eng)
    s = sessionmaker(bind=eng, expire_on_commit=False)()
    yield s
    s.close()
