import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser
import time
import json
import re

# Cabeçalho para simular um navegador real (evita bloqueios simples)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8"
}

# Cache para não baixar o robots.txt toda hora e para controlar o tempo de espera
_robots_cache = {}
_last_request_time = {}


def get_robots_parser(domain):
    """Baixa e guarda em cache o robots.txt do domínio."""
    if domain not in _robots_cache:
        rp = RobotFileParser()
        rp.set_url(f"https://{domain}/robots.txt")
        try:
            rp.read()
        except Exception:
            pass  # Se falhar, assume que pode acessar
        _robots_cache[domain] = rp
    return _robots_cache[domain]


def get_html(url, js=False):
    """Baixa o HTML da página, respeitando robots.txt e com pausas."""
    domain = urlparse(url).netloc
    rp = get_robots_parser(domain)

    # Verifica permissão no robots.txt
    if not rp.can_fetch(HEADERS["User-Agent"], url):
        print(f"[AVISO] Acesso bloqueado pelo robots.txt: {url}")
        return ""

    # Pausa de 3 segundos entre requisições ao mesmo domínio
    agora = time.time()
    if domain in _last_request_time:
        tempo_desde_ultima = agora - _last_request_time[domain]
        if tempo_desde_ultima < 3:
            time.sleep(3 - tempo_desde_ultima)

    _last_request_time[domain] = time.time()

    if js:
        try:
            from playwright.sync_api import sync_playwright
            print(f"[Playwright] Abrindo navegador para: {url}")
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page(user_agent=HEADERS["User-Agent"])
                page.goto(url, timeout=25000)
                html = page.content()
                browser.close()
                return html
        except ImportError:
            print("[ERRO] Playwright não está instalado. Rode: pip install playwright e playwright install chromium")
            return ""
        except Exception as e:
            print(f"[ERRO] Falha ao usar Playwright: {e}")
            return ""

    # Requisição normal (requests)
    try:
        print(f"[Requests] Baixando: {url}")
        resp = requests.get(url, headers=HEADERS, timeout=25)
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        print(f"[ERRO] Falha ao baixar {url}: {e}")
        return ""


def extract_job_links(html, base_url, limit=25):
    """Encontra links que parecem ser de vagas na página."""
    soup = BeautifulSoup(html, 'html.parser')
    links = []

    palavras_chave = ['vaga', 'job', 'career', 'carreira', 'oportunidade',
                      'position', 'opening', 'apply', 'candidat', 'posting']

    for a in soup.find_all('a', href=True):
        href = a['href'].strip()
        texto = a.get_text(strip=True).lower()

        # Ignora links óbvios que não são vagas
        if href.startswith(('mailto:', 'tel:', 'javascript:', '#')):
            continue
        if any(x in href.lower() for x in
               ['facebook.com', 'instagram.com', 'twitter.com', 'youtube.com', 'tiktok.com', 'whatsapp.com']):
            continue

        url_absoluta = urljoin(base_url, href).split('#')[0]

        # Verifica se o link ou o texto tem a ver com vagas
        href_lower = url_absoluta.lower()
        if any(palavra in href_lower or palavra in texto for palavra in palavras_chave):
            if url_absoluta != base_url and url_absoluta not in links:
                links.append(url_absoluta)

        if len(links) >= limit:
            break

    return links


def page_text(html):
    """Limpa o HTML e extrai o texto principal, priorizando JSON-LD de vagas."""
    soup = BeautifulSoup(html, 'html.parser')
    texto_extraido = ""

    # 1. Tenta pegar os dados do JSON-LD (muito comum em sites de emprego)
    for script in soup.find_all('script', type='application/ld+json'):
        try:
            data = json.loads(script.string)
            # As vezes o JSON-LD vem como uma lista
            if isinstance(data, list):
                for item in data:
                    if item.get('@type') == 'JobPosting':
                        texto_extraido += f"Título: {item.get('title', '')}\nEmpresa: {item.get('hiringOrganization', {}).get('name', '')}\nDescrição: {item.get('description', '')}\n\n"
            elif isinstance(data, dict) and data.get('@type') == 'JobPosting':
                texto_extraido += f"Título: {data.get('title', '')}\nEmpresa: {data.get('hiringOrganization', {}).get('name', '')}\nDescrição: {data.get('description', '')}\n\n"
        except:
            continue

    # 2. Remove lixo (scripts, menus, rodapés)
    for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'noscript', 'svg', 'iframe']):
        tag.decompose()

    # 3. Pega o texto limpo
    texto_limpo = soup.get_text(separator='\n', strip=True)

    # Junta o JSON-LD com o resto do texto (se houver)
    texto_final = texto_extraido + "\n---\n" + texto_limpo

    # Remove linhas em branco repetidas
    texto_final = re.sub(r'\n{3,}', '\n\n', texto_final)

    # Corta em 7000 caracteres para não estourar os tokens da IA
    return texto_final[:7000]


# --- TESTE MANUAL ---
if __name__ == '__main__':
    import sys

    if len(sys.argv) > 1:
        url_teste = sys.argv[1]
        print(f"Testando raspagem em: {url_teste}")
        html = get_html(url_teste)
        if html:
            links = extract_job_links(html, url_teste, limit=5)
            print(f"\nLinks encontrados ({len(links)}):")
            for link in links:
                print(f" - {link}")

            print("\n--- Texto da Página (primeiros 500 caracteres) ---")
            print(page_text(html)[:500])
    else:
        print("Uso: python fetch.py https://site-de-vagas.com")