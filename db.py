import sqlite3
import json
from datetime import datetime
from pathlib import Path
import re
import csv

# Garante que a pasta data existe
DB_DIR = Path("data")
DB_DIR.mkdir(exist_ok=True)
DB_PATH = DB_DIR / "vagas.db"


def conn():
    """Cria a conexão com o banco de dados."""
    return sqlite3.connect(DB_PATH)


def init_db():
    """Cria as tabelas se não existirem."""
    with conn() as c:
        # Tabela de Vagas
        c.execute('''
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE NOT NULL,
                title TEXT, company TEXT, location TEXT,
                score INTEGER,
                status TEXT NOT NULL DEFAULT 'para_avaliar',
                reason TEXT, discard_reason TEXT, cover_letter TEXT,
                source TEXT,
                found_at TEXT, updated_at TEXT,
                notes TEXT
            )
        ''')
        # Tabela de Sites Monitorados
        c.execute('''
            CREATE TABLE IF NOT EXISTS sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT, url TEXT UNIQUE, js INTEGER DEFAULT 0, last_run TEXT
            )
        ''')
        # Tabela de Eventos de E-mail
        c.execute('''
            CREATE TABLE IF NOT EXISTS email_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_uid TEXT UNIQUE, account TEXT, subject TEXT, kind TEXT,
                received_at TEXT, notified INTEGER DEFAULT 0
            )
        ''')
        # NOVA TABELA: Perfil do Usuário (salvo pelo painel web)
        c.execute('''
            CREATE TABLE IF NOT EXISTS user_profile (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                data_json TEXT NOT NULL
            )
        ''')


def normalize_url(url):
    """Limpa a URL para evitar duplicatas (remove parâmetros utm_ e #)."""
    if not url: return ""
    url = url.split('#')[0]
    url = re.sub(r'[?&]utm_[^&]+', '', url)
    return url


def url_known(url):
    """Verifica se a URL já está no banco."""
    url = normalize_url(url)
    with conn() as c:
        res = c.execute("SELECT id FROM jobs WHERE url = ?", (url,)).fetchone()
        return res is not None


def save_job(**campos):
    """Salva uma nova vaga ou ignora se a URL já existir."""
    if 'url' in campos:
        campos['url'] = normalize_url(campos['url'])
    campos['found_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    campos['updated_at'] = campos['found_at']

    colunas = ', '.join(campos.keys())
    placeholders = ', '.join(['?'] * len(campos))
    sql = f"INSERT OR IGNORE INTO jobs ({colunas}) VALUES ({placeholders})"

    with conn() as c:
        c.execute(sql, tuple(campos.values()))


def set_status(job_id, status):
    with conn() as c:
        c.execute("UPDATE jobs SET status = ?, updated_at = ? WHERE id = ?",
                  (status, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), job_id))


def set_notes(job_id, texto):
    with conn() as c:
        c.execute("UPDATE jobs SET notes = ?, updated_at = ? WHERE id = ?",
                  (texto, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), job_id))


def list_jobs():
    with conn() as c:
        c.row_factory = sqlite3.Row
        # Ordena: descartadas no fim, depois por nota (maior primeiro)
        res = c.execute('''
            SELECT * FROM jobs 
            ORDER BY (status = 'descartada') ASC, score DESC, found_at DESC
        ''').fetchall()
        return [dict(row) for row in res]


def counts():
    with conn() as c:
        res = c.execute("SELECT status, COUNT(*) as qtd FROM jobs GROUP BY status").fetchall()
        total = c.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
        dic = {status: qtd for status, qtd in res}
        dic['total'] = total
        return dic


def add_source(name, url, js=False):
    url = normalize_url(url)
    with conn() as c:
        c.execute("INSERT OR IGNORE INTO sources (name, url, js) VALUES (?, ?, ?)", (name, url, 1 if js else 0))


def remove_source(source_id):
    with conn() as c:
        c.execute("DELETE FROM sources WHERE id = ?", (source_id,))


def list_sources():
    with conn() as c:
        c.row_factory = sqlite3.Row
        return [dict(r) for r in c.execute("SELECT * FROM sources").fetchall()]


def touch_source(source_id):
    with conn() as c:
        c.execute("UPDATE sources SET last_run = ? WHERE id = ?",
                  (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), source_id))


def export_csv(caminho):
    with conn() as c:
        c.row_factory = sqlite3.Row
        rows = c.execute("SELECT * FROM jobs").fetchall()
        with open(caminho, 'w', newline='', encoding='utf-8') as f:
            if rows:
                writer = csv.DictWriter(f, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows([dict(r) for r in rows])


# --- FUNÇÕES DO PERFIL (Para o Painel Web) ---
def save_profile(data_dict):
    """Salva os dados do formulário do painel como JSON no banco."""
    with conn() as c:
        json_str = json.dumps(data_dict, ensure_ascii=False)
        c.execute("INSERT OR REPLACE INTO user_profile (id, data_json) VALUES (1, ?)", (json_str,))


def get_profile():
    """Pega os dados do perfil. Retorna um dicionário vazio se não existir."""
    with conn() as c:
        res = c.execute("SELECT data_json FROM user_profile WHERE id = 1").fetchone()
        if res:
            return json.loads(res[0])
        return {}


# Inicializa o banco na importação
init_db()