import yaml
import time
from datetime import datetime
from pathlib import Path
import db
import fetch
import score

# Garante que a pasta de logs existe
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)


def salvar_log(mensagem, log_func=print):
    """Imprime no terminal/painel e salva no arquivo de log do dia."""
    log_func(mensagem)
    data_hoje = datetime.now().strftime("%Y-%m-%d")
    arquivo_log = LOG_DIR / f"{data_hoje}.txt"
    with open(arquivo_log, "a", encoding="utf-8") as f:
        hora = datetime.now().strftime("%H:%M:%S")
        f.write(f"[{hora}] {mensagem}\n")


def run_once(log=print) -> dict:
    """Executa uma rodada completa de busca e avaliação."""
    estatisticas = {"analisadas": 0, "para_avaliar": 0, "descartadas": 0, "erros": 0}
    salvar_log("=== INICIANDO RODADA DO AGENTE ===", log)

    # 1. Carregar configurações
    try:
        with open("config.yaml", "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
    except Exception as e:
        salvar_log(f"[ERRO FATAL] Não foi possível ler o config.yaml: {e}", log)
        return estatisticas

    min_score = config.get("min_score", 65)
    max_new_per_run = config.get("max_new_per_run", 30)
    limit_links = config.get("max_links_per_site", 25)

    # 2. Carregar perfil do usuário (do banco de dados, preenchido pelo painel)
    perfil = db.get_profile()
    if not perfil or not perfil.get("nome"):
        salvar_log("[ERRO FATAL] Perfil não preenchido! Vá no painel web e preencha seus dados antes de rodar.", log)
        return estatisticas

    salvar_log(f"Perfil carregado: {perfil.get('nome')}", log)

    # 3. Sincronizar e buscar sites
    sites = db.list_sources()
    if not sites:
        salvar_log("[AVISO] Nenhum site cadastrado. Adicione sites no painel.", log)
        return estatisticas

    vagas_processadas_nesta_rodada = 0

    for site in sites:
        if vagas_processadas_nesta_rodada >= max_new_per_run:
            salvar_log(f"[LIMITE] Limite de {max_new_per_run} vagas por rodada atingido. Parando.", log)
            break

        salvar_log(f"\n--- Analisando site: {site['name']} ({site['url']}) ---", log)
        html = fetch.get_html(site['url'], js=bool(site['js']))

        if not html:
            salvar_log(f"[ERRO] Não foi possível baixar o HTML de {site['name']}.", log)
            estatisticas["erros"] += 1
            continue

        links = fetch.extract_job_links(html, site['url'], limit=limit_links)
        salvar_log(f"Encontrados {len(links)} links de vagas.", log)

        for link in links:
            if vagas_processadas_nesta_rodada >= max_new_per_run:
                break

            if db.url_known(link):
                continue  # Pula se já foi analisada no passado

            salvar_log(f"Avaliando nova vaga: {link}", log)

            try:
                # Baixa a página da vaga
                html_vaga = fetch.get_html(link, js=bool(site['js']))
                if not html_vaga:
                    estatisticas["erros"] += 1
                    continue

                texto_vaga = fetch.page_text(html_vaga)
                if len(texto_vaga) < 200:
                    salvar_log("[IGNORADO] Texto muito curto ou página vazia.", log)
                    continue

                # Chama o DeepSeek para avaliar
                avaliacao = score.evaluate(texto_vaga, link, perfil)
                if not avaliacao:
                    estatisticas["erros"] += 1
                    continue

                vagas_processadas_nesta_rodada += 1
                estatisticas["analisadas"] += 1

                # Se não for vaga, descarta
                if not avaliacao.get('is_job_posting'):
                    db.save_job(url=link, title="Página não é vaga", status="descartada",
                                discard_reason="Página não é uma vaga específica", source=site['name'])
                    estatisticas["descartadas"] += 1
                    continue

                nota = avaliacao['score']
                titulo = avaliacao.get('title', 'Vaga sem título')
                empresa = avaliacao.get('company', 'Empresa não informada')
                local = avaliacao.get('location', 'Local não informado')

                if nota >= min_score:
                    # Vaga boa! Gera a carta
                    salvar_log(f"[APROVADA] Nota {nota}: {titulo} na {empresa}", log)
                    carta = score.write_letter(texto_vaga, avaliacao, perfil)
                    db.save_job(
                        url=link, title=titulo, company=empresa, location=local,
                        score=nota, status="para_avaliar", reason=avaliacao['reason'],
                        cover_letter=carta, source=site['name']
                    )
                    estatisticas["para_avaliar"] += 1
                else:
                    # Vaga ruim
                    salvar_log(f"[DESCARTADA] Nota {nota}: {titulo} na {empresa}", log)
                    db.save_job(
                        url=link, title=titulo, company=empresa, location=local,
                        score=nota, status="descartada", reason=avaliacao['reason'],
                        discard_reason=avaliacao['discard_reason'], source=site['name']
                    )
                    estatisticas["descartadas"] += 1

            except Exception as e:
                salvar_log(f"[ERRO] Falha ao processar vaga {link}: {e}", log)
                estatisticas["erros"] += 1
                continue  # Erro em uma vaga não derruba a rodada

        db.touch_source(site['id'])

    salvar_log("\n=== RODADA FINALIZADA ===", log)
    salvar_log(
        f"Analisadas: {estatisticas['analisadas']} | Novas boas: {estatisticas['para_avaliar']} | Descartadas: {estatisticas['descartadas']} | Erros: {estatisticas['erros']}",
        log)
    return estatisticas