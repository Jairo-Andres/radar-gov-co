import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def axe_raw():
    return json.loads((FIXTURES / "axe_result.json").read_text(encoding="utf-8"))


@pytest.fixture
def lhr_mobile():
    return json.loads((FIXTURES / "lighthouse_mobile.json").read_text(encoding="utf-8"))


def make_record(site_id="dane", **extra):
    """Registro de sitio mínimo, como lo deja el auditor antes de puntuar."""
    record = {
        "id": site_id,
        "name": site_id.upper(),
        "category": "Entidad nacional",
        "url": f"https://www.{site_id}.gov.co/",
        "status": "ok",
        "pages": [],
        "mobile": None,
        "lighthouse": {"mobile": None, "desktop": None},
        "errors": [],
    }
    record.update(extra)
    return record
