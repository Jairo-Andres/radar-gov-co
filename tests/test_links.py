from radar import links

HOME = "https://www.dane.gov.co/"


def allow_all(_url):
    return True


def test_pick_internal_pages_filters_and_keeps_order():
    hrefs = [
        "https://www.dane.gov.co/",  # el propio inicio
        "https://www.dane.gov.co/#contenido",  # ancla al inicio
        "https://otro.gov.co/pagina",  # otro sitio
        "https://www.dane.gov.co/login",  # acceso: nunca
        "https://www.dane.gov.co/informe.pdf",  # archivo
        "https://www.dane.gov.co/buscar?q=censo",  # búsqueda / parámetros
        "mailto:contacto@example.org",
        "https://dane.gov.co/estadisticas",  # mismo sitio sin www
        "https://www.dane.gov.co/estadisticas/",  # repetida
        "https://www.dane.gov.co/servicios",
        "https://www.dane.gov.co/tercera",
    ]
    assert links.pick_internal_pages(HOME, hrefs, allow_all, 2) == [
        "https://dane.gov.co/estadisticas",
        "https://www.dane.gov.co/servicios",
    ]


def test_pick_internal_pages_respects_robots():
    hrefs = ["https://www.dane.gov.co/privado/a", "https://www.dane.gov.co/publico"]
    picked = links.pick_internal_pages(HOME, hrefs, lambda u: "/privado/" not in u, 2)
    assert picked == ["https://www.dane.gov.co/publico"]


def test_pick_internal_pages_zero():
    assert links.pick_internal_pages(HOME, ["https://www.dane.gov.co/a"], allow_all, 0) == []


def test_ignored_failures():
    assert links.is_ignored_failure("net::ERR_ABORTED")
    assert not links.is_ignored_failure("net::ERR_NAME_NOT_RESOLVED")
    assert not links.is_ignored_failure(None)


def test_unique_failed_and_first_party():
    pages = [
        {"failed_resources": [{"url": "https://www.dane.gov.co/a.png"}, {"url": "https://cdn.example.com/x.js"}]},
        {"failed_resources": [{"url": "https://www.dane.gov.co/a.png"}]},
    ]
    urls = [b["url"] for b in links.unique_failed(pages)]
    assert urls == ["https://www.dane.gov.co/a.png", "https://cdn.example.com/x.js"]
    assert links.is_first_party("https://static.dane.gov.co/a.css", HOME)
    assert not links.is_first_party("https://cdn.example.com/x.js", HOME)


def test_pick_internal_pages_skips_home_redirect_target():
    hrefs = ["https://www.dian.gov.co/Paginas/Inicio.aspx", "https://www.dian.gov.co/tramites"]
    picked = links.pick_internal_pages(
        "https://www.dian.gov.co/", hrefs, allow_all, 1, home_aliases=("https://www.dian.gov.co/Paginas/Inicio.aspx",)
    )
    assert picked == ["https://www.dian.gov.co/tramites"]
