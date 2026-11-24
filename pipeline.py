
import yaml
from datetime import datetime
from pathlib import Path

import db
import fetch
import score


LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)


def salvar_log(mensagem, log_func=print):
    """Imprime e salva o registro da execução."""
    log_func(mensagem)

    data_hoje = datetime.now().strftime("%Y-%m-%d")
    arquivo_log = LOG_DIR / f"{data_hoje}.txt"

    with open(arquivo_log, "a", encoding="utf-8") as f:
        hora = datetime.now().strftime("%H:%M:%S")
        f.write(f"[{hora}] {mensagem}\n")


def run_once(log=print, filtros=None) -> dict:
    """Executa uma rodada de busca e avaliação de vagas."""

    estatisticas = {
        "encontradas": 0,
        "analisadas": 0,
        "para_avaliar": 0,
        "descartadas": 0,
        "ignoradas": 0,
        "erros": 0,
    }

    filtros = filtros or {}

    estado_filtro = str(
        filtros.get("estado") or ""
    ).strip()

    cidade_filtro = str(
        filtros.get("cidade") or ""
    ).strip()

    salvar_log("=== INICIANDO RODADA DO AGENTE ===", log)

    # 1. Configurações
    try:
        with open("config.yaml", "r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}

    except Exception as e:
        salvar_log(
            f"[ERRO FATAL] Não foi possível ler config.yaml: {e}",
            log
        )
        return estatisticas

    min_score = config.get("min_score", 65)
    max_new_per_run = config.get("max_new_per_run", 30)
    limit_links = config.get("max_links_per_site", 25)

    # 2. Perfil
    try:
        perfil = db.get_profile()
    except Exception as e:
        salvar_log(f"[ERRO] Falha ao carregar perfil: {e}", log)
        estatisticas["erros"] += 1
        return estatisticas

    if not perfil or not perfil.get("nome"):
        salvar_log(
            "[ERRO FATAL] Perfil não preenchido! "
            "Acesse Meu Perfil antes de executar.",
            log
        )
        return estatisticas

    salvar_log(
        f"Perfil carregado: {perfil.get('nome')}",
        log
    )

    # 3. Filtros geográficos
    salvar_log(
        f"Estado selecionado: {estado_filtro or 'Todos'}",
        log
    )

    salvar_log(
        f"Cidade selecionada: {cidade_filtro or 'Todas'}",
        log
    )

    # 4. Fontes cadastradas
    try:
        sites = db.list_sources() or []
    except Exception as e:
        salvar_log(f"[ERRO] Falha ao consultar sites: {e}", log)
        estatisticas["erros"] += 1
        return estatisticas

    if not sites:
        salvar_log(
            "[AVISO] Nenhum site cadastrado. "
            "Adicione uma fonte em Configurações.",
            log
        )
        return estatisticas

    vagas_processadas = 0

    # 5. Percorrer sites
    for site in sites:

        if vagas_processadas >= max_new_per_run:
            salvar_log(
                f"[LIMITE] Limite de {max_new_per_run} "
                "vagas processadas atingido.",
                log
            )
            break

        nome_site = site.get("name", "Site")
        url_original = site.get("url", "")

        salvar_log(
            f"\n--- Analisando site: {nome_site} "
            f"({url_original}) ---",
            log
        )

        # Aplica filtros na busca global da Gupy.
        url_busca = fetch.build_gupy_search_url(
            url_original,
            state=estado_filtro,
            city=cidade_filtro
        )

        if url_busca != url_original:
            salvar_log(
                f"[FILTROS GUPY] Estado: "
                f"{estado_filtro or 'Todos'} | "
                f"Cidade: {cidade_filtro or 'Todas'}",
                log
            )

            salvar_log(
                f"[URL DE BUSCA] {url_busca}",
                log
            )

        # 6. Baixar página de resultados
        try:
            html = fetch.get_html(
                url_busca,
                js=bool(site.get("js"))
            )

        except Exception as e:
            salvar_log(
                f"[ERRO] Falha ao baixar página de busca: {e}",
                log
            )
            estatisticas["erros"] += 1
            continue

        if not html:
            salvar_log(
                f"[ERRO] Não foi possível baixar {nome_site}.",
                log
            )
            estatisticas["erros"] += 1
            continue

        # 7. Extrair anúncios individuais
        try:
            links = fetch.extract_job_links(
                html,
                url_busca,
                limit=limit_links
            )

        except Exception as e:
            salvar_log(
                f"[ERRO] Falha ao extrair links: {e}",
                log
            )
            estatisticas["erros"] += 1
            continue

        estatisticas["encontradas"] += len(links)

        salvar_log(
            f"Encontrados {len(links)} links de vagas reais.",
            log
        )

        if not links:
            salvar_log(
                "[AVISO] Nenhum anúncio individual foi encontrado. "
                "A página pode exigir outro método de extração.",
                log
            )

        # 8. Avaliar cada vaga
        for link in links:

            if vagas_processadas >= max_new_per_run:
                break

            try:
                if db.url_known(link):
                    salvar_log(
                        f"[JÁ EXISTENTE] Vaga ignorada: {link}",
                        log
                    )
                    continue

                salvar_log(
                    f"Avaliando nova vaga: {link}",
                    log
                )

                html_vaga = fetch.get_html(
                    link,
                    js=bool(site.get("js"))
                )

                if not html_vaga:
                    salvar_log(
                        "[ERRO] Não foi possível abrir a página da vaga.",
                        log
                    )
                    estatisticas["erros"] += 1
                    continue

                texto_vaga = fetch.page_text(html_vaga)

                if len(texto_vaga.strip()) < 200:
                    salvar_log(
                        f"[IGNORADA] Descrição insuficiente: "
                        f"{len(texto_vaga)} caracteres.",
                        log
                    )
                    estatisticas["ignoradas"] += 1
                    continue

                # 9. Avaliação pela IA
                avaliacao = score.evaluate(
                    texto_vaga,
                    link,
                    perfil
                )

                if not avaliacao:
                    salvar_log(
                        "[ERRO] A IA não conseguiu avaliar a vaga.",
                        log
                    )
                    estatisticas["erros"] += 1
                    continue

                vagas_processadas += 1
                estatisticas["analisadas"] += 1

                if not avaliacao.get("is_job_posting"):
                    db.save_job(
                        url=link,
                        title="Página não é vaga",
                        status="descartada",
                        discard_reason=(
                            "Página não é uma vaga específica"
                        ),
                        source=nome_site
                    )

                    estatisticas["descartadas"] += 1
                    continue

                nota = avaliacao.get("score", 0)
                titulo = avaliacao.get(
                    "title",
                    "Vaga sem título"
                )
                empresa = avaliacao.get(
                    "company",
                    "Empresa não informada"
                )
                local = avaliacao.get(
                    "location",
                    "Local não informado"
                )

                # 10. Aprovar ou descartar
                if nota >= min_score:

                    salvar_log(
                        f"[APROVADA] Nota {nota}: "
                        f"{titulo} na {empresa}",
                        log
                    )

                    carta = score.write_letter(
                        texto_vaga,
                        avaliacao,
                        perfil
                    )

                    db.save_job(
                        url=link,
                        title=titulo,
                        company=empresa,
                        location=local,
                        score=nota,
                        status="para_avaliar",
                        reason=avaliacao.get("reason", ""),
                        cover_letter=carta,
                        source=nome_site
                    )

                    estatisticas["para_avaliar"] += 1

                else:

                    salvar_log(
                        f"[DESCARTADA] Nota {nota}: "
                        f"{titulo} na {empresa}",
                        log
                    )

                    db.save_job(
                        url=link,
                        title=titulo,
                        company=empresa,
                        location=local,
                        score=nota,
                        status="descartada",
                        reason=avaliacao.get("reason", ""),
                        discard_reason=avaliacao.get(
                            "discard_reason",
                            ""
                        ),
                        source=nome_site
                    )

                    estatisticas["descartadas"] += 1

            except Exception as e:
                salvar_log(
                    f"[ERRO] Falha ao processar vaga {link}: {e}",
                    log
                )
                estatisticas["erros"] += 1
                continue

        # 11. Atualizar data da fonte
        try:
            db.touch_source(site["id"])
        except Exception as e:
            salvar_log(
                f"[AVISO] Não foi possível atualizar a fonte: {e}",
                log
            )

    # 12. Resumo
    salvar_log("\n=== RODADA FINALIZADA ===", log)

    salvar_log(
        f"Encontradas: {estatisticas['encontradas']} | "
        f"Analisadas: {estatisticas['analisadas']} | "
        f"Ignoradas: {estatisticas['ignoradas']} | "
        f"Novas boas: {estatisticas['para_avaliar']} | "
        f"Descartadas: {estatisticas['descartadas']} | "
        f"Erros: {estatisticas['erros']}",
        log
    )

    return estatisticas
