import pytest

from radar.config import MAX_PAGES_PER_SITE, MIN_PAUSE_SECONDS, load_config
from radar.robots import Robots, robots_from_response, robots_url_for


def test_robots_rules_for_radar_agent():
    robots = Robots.from_text("User-agent: RadarGovCo\nDisallow: /privado/\n\nUser-agent: *\nDisallow: /\n")
    assert robots.allowed("https://x.gov.co/publico")
    assert not robots.allowed("https://x.gov.co/privado/a")


def test_robots_wildcard_applies_to_radar():
    robots = Robots.from_text("User-agent: *\nDisallow: /admin\nCrawl-delay: 10\n")
    assert robots.allowed("https://x.gov.co/")
    assert not robots.allowed("https://x.gov.co/admin/panel")
    assert robots.crawl_delay() == 10


@pytest.mark.parametrize("status,text,error,allowed_home,state", [
    (200, "User-agent: *\nDisallow: /\n", None, False, "ok"),
    (404, None, None, True, "sin robots.txt (404)"),
    (403, None, None, False, "robots.txt no disponible (403)"),
    (503, None, None, False, "robots.txt no disponible (503)"),
    (None, None, "timeout", False, "robots.txt no disponible (timeout)"),
    (200, "<!DOCTYPE html><html><body>Inicio</body></html>", None, True,
     "robots.txt devuelve HTML (se trata como inexistente)"),
])
def test_robots_from_response(status, text, error, allowed_home, state):
    robots, description = robots_from_response(status, text, error)
    assert robots.allowed("https://x.gov.co/") is allowed_home
    assert description == state


def test_robots_url_for():
    assert robots_url_for("https://www.dian.gov.co/inicio?x=1") == "https://www.dian.gov.co/robots.txt"


def write(tmp_path, body):
    path = tmp_path / "sites.yaml"
    path.write_text(body, encoding="utf-8")
    return path


def test_config_enforces_ethical_limits(tmp_path):
    path = write(tmp_path, "settings: {pause_seconds: 0, max_pages: 50}\nsites:\n"
                           "  - {id: dane, name: DANE, url: 'https://www.dane.gov.co/', category: Entidad}\n")
    settings, sites = load_config(path)
    assert settings.pause_seconds == MIN_PAUSE_SECONDS
    assert settings.max_pages == MAX_PAGES_PER_SITE
    assert sites[0].host == "www.dane.gov.co"


def test_config_rejects_non_gov_domains(tmp_path):
    path = write(tmp_path, "sites:\n  - {id: x, name: X, url: 'https://example.com/', category: Otro}\n")
    with pytest.raises(ValueError, match="gov.co"):
        load_config(path)


def test_config_rejects_duplicate_ids(tmp_path):
    site = "  - {id: dane, name: DANE, url: 'https://www.dane.gov.co/', category: E}\n"
    with pytest.raises(ValueError, match="repetidos"):
        load_config(write(tmp_path, "sites:\n" + site + site))


def test_real_sites_file_is_valid():
    _, sites = load_config("sites.yaml")
    assert len(sites) == 30
