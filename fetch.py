
import json
import re
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
}

_robots_cache = {}
_last_request_time = {}
_playwright_ready = False


def log(message):
    print(message, flush=True)


def get_robots_parser(url):
    """Consulta robots.txt e guarda o resultado em cache."""
    parsed = urlparse(url)
    domain = parsed.netloc

    if domain in _robots_cache:
        return _robots_cache[domain]

    robots_url = f"{parsed.scheme}://{domain}/robots.txt"
    rp = RobotFileParser()
    rp.set_url(robots_url)

    try:
        response = requests.get(
            robots_url,
            headers=HEADERS,
            timeout=10
        )

        if response.status_code == 404:
            rp.parse([])
        elif response.status_code >= 400:
            rp.parse(["User-agent: *", "Disallow: /"])
        else:
            rp.parse(response.text.splitlines())

    except requests.RequestException as e:
        log(f"[ERRO] Não foi possível consultar robots.txt: {e}")
        rp.parse(["User-agent: *", "Disallow: /"])

    _robots_cache[domain] = rp
    return rp


def permitido_por_robots(url):
    rp = get_robots_parser(url)
    permitido = rp.can_fetch(HEADERS["User-Agent"], url)

    if not permitido:
        log(f"[AVISO] Acesso não permitido pelo robots.txt: {url}")

    return permitido


def respeitar_intervalo(domain):
    """Mantém intervalo mínimo entre requisições ao mesmo domínio."""
    agora = time.time()
    ultima = _last_request_time.get(domain, 0)
    espera = 3 - (agora - ultima)

    if espera > 0:
        time.sleep(espera)

    _last_request_time[domain] = time.time()


def instalar_chromium():
    """Instala o Chromium uma única vez, se necessário."""
    global _playwright_ready

    if _playwright_ready:
        return True

    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            executavel = Path(p.chromium.executable_path)

            if not executavel.is_file():
                log("[Playwright] Chromium não encontrado.")
                log("[Playwright] Instalando Chromium. Aguarde...")

                resultado = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "playwright",
                        "install",
                        "chromium",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=300,
                )

                if resultado.returncode != 0:
                    log("[ERRO] Não foi possível instalar o Chromium.")
                    log(resultado.stderr[-3000:])
                    return False

            if not Path(p.chromium.executable_path).is_file():
                log("[ERRO] Chromium continua indisponível.")
                return False

        _playwright_ready = True
        log("[Playwright] Chromium pronto para uso.")
        return True

    except subprocess.TimeoutExpired:
        log("[ERRO] A instalação do Chromium excedeu o tempo limite.")
        return False

    except Exception as e:
        log(f"[ERRO] Falha na preparação do Chromium: {e}")
        return False


def baixar_com_playwright(url):
    """Abre páginas que dependem de JavaScript."""
    if not instalar_chromium():
        return ""

    try:
        from playwright.sync_api import sync_playwright

        log(f"[Playwright] Abrindo: {url}")

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)

            try:
                page = browser.new_page(
                    user_agent=HEADERS["User-Agent"],
                    locale="pt-BR",
                )

                response = page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=30000,
                )

                if response and response.status >= 400:
                    log(
                        f"[ERRO] Página respondeu com HTTP "
                        f"{response.status}: {url}"
                    )
                    return ""

                page.wait_for_timeout(1500)

                titulo = page.title().lower()

                if any(
                    termo in titulo
                    for termo in ["captcha", "access denied", "acesso negado"]
                ):
                    log("[AVISO] Página apresentou bloqueio de acesso.")
                    return ""

                return page.content()

            finally:
                browser.close()

    except Exception as e:
        log(f"[ERRO] Falha no Playwright: {e}")
        return ""


def get_html(url, js=False):
    """Baixa HTML respeitando robots.txt e intervalo entre requisições."""
    parsed = urlparse(url)

    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        log(f"[ERRO] URL inválida: {url}")
        return ""

    domain = parsed.netloc

    if not permitido_por_robots(url):
        return ""

    respeitar_intervalo(domain)

    if js:
        return baixar_com_playwright(url)

    try:
        log(f"[Requests] Baixando: {url}")

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=25,
        )

        response.raise_for_status()
        return response.text

    except requests.RequestException as e:
        log(f"[ERRO] Falha ao baixar {url}: {e}")
        return ""


def build_gupy_search_url(base_url, state="", city=""):
    """Aplica filtros de estado e cidade à busca global da Gupy."""
    parsed = urlparse(base_url)

    if (
        parsed.netloc.lower() != "portal.gupy.io"
        or "/job-search" not in parsed.path
    ):
        return base_url

    prefix, marker, tail = parsed.path.partition("/job-search/")

    if not marker:
        prefix = parsed.path.rstrip("/")
        tail = ""

    partes = [
        p for p in re.split(r"[&/]", tail) if p
    ]

    partes += [
        p for p in parsed.query.split("&") if p
    ]

    partes = [
        p for p in partes
        if not p.lower().startswith(("state=", "city="))
    ]

    from urllib.parse import quote

    if state:
        partes.append("state=" + quote(str(state), safe=""))

    if city:
        partes.append("city=" + quote(str(city), safe=""))

    caminho = prefix.rstrip("/") + "/job-search"

    if partes:
        caminho += "/" + "&".join(partes)

    return parsed._replace(
        path=caminho,
        query=""
    ).geturl()


def extract_job_links(html, base_url, limit=25):
    """Extrai anúncios individuais e ignora páginas de filtros."""
    soup = BeautifulSoup(html, "html.parser")
    links = []

    portal_gupy = (
        urlparse(base_url).netloc.lower() == "portal.gupy.io"
    )

    sociais = (
        "facebook.com",
        "instagram.com",
        "twitter.com",
        "youtube.com",
        "tiktok.com",
        "whatsapp.com",
    )

    def anuncio(url):
        parsed = urlparse(url)
        host = parsed.netloc.lower()
        path = parsed.path.lower()

        if any(s in host for s in sociais):
            return False

        if (
            "job-search" in path
            or "/state=" in path
            or "/city=" in path
        ):
            return False

        rota_vaga = re.search(
            r"/(?:job|jobs|candidates/jobs)/[^/]+",
            path
        )

        if portal_gupy or host.endswith(".gupy.io"):
            return (
                host.endswith(".gupy.io")
                and rota_vaga is not None
            )

        termos = (
            "vaga",
            "job",
            "career",
            "carreira",
            "oportunidade",
            "position",
            "opening",
            "apply",
            "candidat",
            "posting",
        )

        return any(t in url.lower() for t in termos)

    for tag in soup.find_all("a", href=True):
        href = tag["href"].strip()

        if href.startswith(
            ("mailto:", "tel:", "javascript:", "#")
        ):
            continue

        url = urljoin(
            base_url,
            href
        ).split("#")[0].rstrip("/")

        if (
            url
            and url != base_url.rstrip("/")
            and anuncio(url)
            and url not in links
        ):
            links.append(url)

            if len(links) >= limit:
                return links

    # Procura também anúncios publicados em dados estruturados.
    for script in soup.find_all(
        "script",
        type="application/ld+json"
    ):
        try:
            data = json.loads(
                script.string or script.get_text()
            )
        except (json.JSONDecodeError, TypeError):
            continue

        pilha = data if isinstance(data, list) else [data]

        while pilha:
            item = pilha.pop()

            if isinstance(item, list):
                pilha.extend(item)

            elif isinstance(item, dict):
                tipo = item.get("@type")

                if (
                    tipo == "JobPosting"
                    or (
                        isinstance(tipo, list)
                        and "JobPosting" in tipo
                    )
                ):
                    destino = (
                        item.get("url")
                        or item.get("sameAs")
                    )

                    if isinstance(destino, str):
                        url = urljoin(
                            base_url,
                            destino
                        ).split("#")[0]

                        if anuncio(url) and url not in links:
                            links.append(url)

                            if len(links) >= limit:
                                return links

                pilha.extend(
                    v
                    for v in item.values()
                    if isinstance(v, (dict, list))
                )

    return links[:limit]


def page_text(html):
    """Extrai texto da página, priorizando dados estruturados de vagas."""
    soup = BeautifulSoup(html, "html.parser")
    texto_extraido = ""

    for script in soup.find_all(
        "script",
        type="application/ld+json"
    ):
        try:
            if not script.string and not script.get_text(strip=True):
                continue

            data = json.loads(
                script.string or script.get_text()
            )

            itens = data if isinstance(data, list) else [data]

            for item in itens:
                if not isinstance(item, dict):
                    continue

                if item.get("@type") != "JobPosting":
                    continue

                empresa = item.get("hiringOrganization", {})

                if isinstance(empresa, dict):
                    nome_empresa = empresa.get("name", "")
                else:
                    nome_empresa = ""

                texto_extraido += (
                    f"Título: {item.get('title', '')}\n"
                    f"Empresa: {nome_empresa}\n"
                    f"Descrição: {item.get('description', '')}\n\n"
                )

        except (
            json.JSONDecodeError,
            TypeError,
            AttributeError
        ):
            continue

    for tag in soup([
        "script",
        "style",
        "nav",
        "footer",
        "header",
        "noscript",
        "svg",
        "iframe",
    ]):
        tag.decompose()

    texto_limpo = soup.get_text(
        separator="\n",
        strip=True,
    )

    texto_final = texto_extraido + "\n---\n" + texto_limpo
    texto_final = re.sub(r"\n{3,}", "\n\n", texto_final)

    return texto_final[:7000]


if __name__ == "__main__":
    if len(sys.argv) > 1:
        url_teste = sys.argv[1]

        print(f"Testando raspagem: {url_teste}")

        html = get_html(url_teste, js=True)

        if html:
            links = extract_job_links(
                html,
                url_teste,
                limit=5,
            )

            print(f"\nLinks encontrados ({len(links)}):")

            for link in links:
                print(f" - {link}")

            print("\n--- Texto da página ---")
            print(page_text(html)[:500])

        else:
            print("Nenhum HTML foi obtido.")

    else:
        print("Uso: python fetch.py https://site-de-vagas.com")
