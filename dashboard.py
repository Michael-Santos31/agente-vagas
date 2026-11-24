
import streamlit as st
import os
import db
import pipeline
import llm

st.set_page_config(page_title="Agente de Vagas", page_icon="🤖", layout="wide")
st.title("🤖 Candidaturas - Agente de Vagas")

aba_vagas, aba_perfil, aba_config = st.tabs(
    ["📊 Painel de Vagas", "👤 Meu Perfil", "⚙️ Configurações e Testes"]
)

# ==========================================
# ABA 2: MEU PERFIL
# ==========================================
with aba_perfil:
    st.header("Meus Dados e Estilo de Escrita")
    perfil_salvo = db.get_profile() or {}

    with st.form("form_perfil"):
        col1, col2 = st.columns(2)

        with col1:
            nome = st.text_input("Seu Nome Completo", value=perfil_salvo.get("nome", ""))
            localizacao = st.text_input("Sua Localização (Cidade/UF)", value=perfil_salvo.get("localizacao", ""))
            salario = st.text_input("Salário Mínimo Desejado", value=perfil_salvo.get("salario_minimo", ""))

        with col2:
            modelos = ["Remoto", "Híbrido", "Presencial", "Indiferente"]
            modelo_salvo = perfil_salvo.get("modelo_trabalho", "Remoto")
            indice = modelos.index(modelo_salvo) if modelo_salvo in modelos else 0

            modelo_trabalho = st.selectbox(
                "Modelo de Trabalho Preferido", modelos, index=indice
            )

            cidades_aceitas = st.text_input(
                "Cidades que aceita",
                value=perfil_salvo.get("cidades_aceitas_txt", "")
            )

            cargos_nao = st.text_input(
                "Cargos que NÃO quer",
                value=perfil_salvo.get("cargos_nao_txt", "")
            )

        resumo = st.text_area(
            "Resumo Profissional",
            value=perfil_salvo.get("resumo", ""),
            height=100
        )

        st.subheader("Habilidades e Formação")

        habilidades_txt = st.text_area(
            "Habilidades",
            value=perfil_salvo.get("habilidades_txt", ""),
            height=80
        )

        formacao = st.text_area(
            "Formação e Cursos",
            value=perfil_salvo.get("formacao", ""),
            height=80
        )

        st.subheader("Experiências")

        experiencias_txt = st.text_area(
            "Experiências Profissionais",
            value=perfil_salvo.get("experiencias_txt", ""),
            height=150
        )

        st.subheader("Meu Jeito de Escrever")

        exemplos = st.text_area(
            "Textos de Exemplo",
            value=perfil_salvo.get("exemplos_escrita_txt", ""),
            height=200
        )

        salvar = st.form_submit_button("💾 Salvar Perfil", type="primary")

        if salvar:
            dados = {
                "nome": nome,
                "localizacao": localizacao,
                "salario_minimo": salario,
                "modelo_trabalho": modelo_trabalho,
                "cidades_aceitas_txt": cidades_aceitas,
                "cargos_nao_txt": cargos_nao,
                "resumo": resumo,
                "habilidades_txt": habilidades_txt,
                "formacao": formacao,
                "experiencias_txt": experiencias_txt,
                "exemplos_escrita_txt": exemplos
            }

            try:
                db.save_profile(dados)
                st.success("Perfil salvo com sucesso!")
            except Exception as e:
                st.error(f"Erro ao salvar perfil: {e}")


# ==========================================
# ABA 1: PAINEL DE VAGAS
# ==========================================
with aba_vagas:

    with st.sidebar:
        st.header("Ações do Agente")

        if st.button(
            "🚀 Buscar vagas agora",
            use_container_width=True,
            type="primary"
        ):

            st.subheader("Registro da busca")

            log_placeholder = st.empty()
            resultado_placeholder = st.empty()
            linhas_log = []

            def escrever_log(msg):
                mensagem = str(msg)
                linhas_log.append(mensagem)

                log_placeholder.code(
                    "\n".join(linhas_log[-100:]),
                    language="text"
                )

            try:
                with st.spinner("O robô está trabalhando. Aguarde..."):
                    stats = pipeline.run_once(log=escrever_log)

                resultado_placeholder.success(
                    "Rodada finalizada!\n\n"
                    f"Analisadas: {stats.get('analisadas', 0)}\n\n"
                    f"Boas: {stats.get('para_avaliar', 0)}\n\n"
                    f"Descartadas: {stats.get('descartadas', 0)}\n\n"
                    f"Erros: {stats.get('erros', 0)}"
                )

                if stats.get("analisadas", 0) == 0:
                    st.warning(
                        "Nenhuma vaga foi analisada. "
                        "Confira os registros acima para identificar o motivo."
                    )

            except Exception as e:
                resultado_placeholder.error(
                    f"Falha durante a busca: {type(e).__name__}: {e}"
                )

                escrever_log(
                    f"[ERRO NÃO TRATADO] {type(e).__name__}: {e}"
                )

        st.divider()

        # ADICIONAR SITE
        st.subheader("Adicionar Site de Vagas")

        with st.form("form_add_site"):
            nome_site = st.text_input("Nome da Empresa/Site")
            url_site = st.text_input("URL da Página de Carreiras")

            usa_js = st.checkbox(
                "O site carrega vagas com JavaScript (ex: Gupy)"
            )

            add_btn = st.form_submit_button("Adicionar Site")

            if add_btn:
                if url_site.startswith(("http://", "https://")):
                    try:
                        db.add_source(
                            nome_site.strip() or url_site,
                            url_site.strip(),
                            usa_js
                        )
                        st.success("Site adicionado!")
                    except Exception as e:
                        st.error(f"Erro ao adicionar site: {e}")
                else:
                    st.error("A URL deve começar com http:// ou https://")

        # SITES MONITORADOS
        st.subheader("Sites Monitorados")

        try:
            sites = db.list_sources()
        except Exception as e:
            sites = []
            st.error(f"Erro ao carregar sites: {e}")

        if not sites:
            st.info("Nenhum site cadastrado.")

        for s in sites:
            col_s1, col_s2 = st.columns([3, 1])

            with col_s1:
                st.caption(
                    f"**{s.get('name', 'Site')}**\n{s.get('url', '')}"
                )

            with col_s2:
                if st.button("🗑️", key=f"del_{s['id']}"):
                    try:
                        db.remove_source(s["id"])
                        st.success("Site removido. Atualize a página.")
                    except Exception as e:
                        st.error(f"Erro ao remover site: {e}")

            st.divider()

    # MÉTRICAS
    st.subheader("Resumo das vagas")

    try:
        contagens = db.counts() or {}
    except Exception as e:
        contagens = {}
        st.error(f"Erro ao consultar métricas: {e}")

    c1, c2, c3, c4, c5 = st.columns(5)

    c1.metric("Analisadas", contagens.get("total", 0))
    c2.metric("Para Avaliar", contagens.get("para_avaliar", 0))
    c3.metric("Candidatadas", contagens.get("candidatada", 0))
    c4.metric("Em Processo", contagens.get("em_processo", 0))
    c5.metric("Descartadas", contagens.get("descartada", 0))

    st.divider()

    # FILTROS
    col_f1, col_f2, col_f3 = st.columns(3)

    with col_f1:
        filtro_status = st.selectbox(
            "Filtrar por Status",
            [
                "Todas",
                "para_avaliar",
                "candidatada",
                "em_processo",
                "pendente",
                "descartada"
            ]
        )

    with col_f2:
        filtro_busca = st.text_input("Buscar empresa ou cargo")

    with col_f3:
        filtro_nota = st.slider("Nota mínima", 0, 100, 0)

    # LISTAR VAGAS
    try:
        vagas = db.list_jobs() or []
    except Exception as e:
        vagas = []
        st.error(f"Erro ao carregar vagas: {e}")

    vagas_filtradas = []

    for v in vagas:
        if filtro_status != "Todas" and v.get("status") != filtro_status:
            continue

        if filtro_nota > 0 and (v.get("score") or 0) < filtro_nota:
            continue

        if filtro_busca:
            busca_lower = filtro_busca.lower()
            titulo = str(v.get("title", "")).lower()
            empresa = str(v.get("company", "")).lower()

            if busca_lower not in titulo and busca_lower not in empresa:
                continue

        vagas_filtradas.append(v)

    if not vagas_filtradas:
        st.info(
            "Nenhuma vaga encontrada com esses filtros. "
            "Execute uma busca ou ajuste os filtros."
        )

    for v in vagas_filtradas:
        score_vaga = v.get("score") or 0
        status_vaga = v.get("status", "")

        icone = (
            "🟢" if score_vaga >= 65
            else "🔴" if status_vaga == "descartada"
            else "🟡"
        )

        titulo_expander = (
            f"{icone} Nota {score_vaga} | "
            f"{v.get('title', 'Sem título')} - "
            f"{v.get('company', 'Empresa não informada')}"
        )

        with st.expander(titulo_expander):

            st.markdown(
                f"**Link:** [Abrir Vaga]({v.get('url', '')})"
            )

            st.markdown(
                f"**Local:** {v.get('location', '')} | "
                f"**Fonte:** {v.get('source', '')} | "
                f"**Encontrada em:** {str(v.get('found_at', ''))[:10]}"
            )

            st.info(
                f"**Justificativa da IA:** {v.get('reason', '')}"
            )

            if status_vaga == "descartada":
                st.error(
                    f"**Motivo do Descarte:** {v.get('discard_reason', '')}"
                )

            carta = v.get("cover_letter")

            if carta:
                st.warning(
                    "⚠️ **Revise antes de usar. A IA pode cometer erros.**"
                )

                if "[REVISAR:" in carta:
                    st.error(
                        "A IA gerou um alerta nesta carta. "
                        "Verifique as informações."
                    )

                st.text_area(
                    "Carta Sugerida",
                    value=carta,
                    height=200,
                    key=f"carta_{v['id']}"
                )

            col_v1, col_v2 = st.columns([1, 2])

            with col_v1:
                opcoes_status = [
                    "para_avaliar",
                    "candidatada",
                    "em_processo",
                    "pendente",
                    "descartada"
                ]

                idx_atual = (
                    opcoes_status.index(status_vaga)
                    if status_vaga in opcoes_status
                    else 0
                )

                novo_status = st.selectbox(
                    "Status",
                    opcoes_status,
                    index=idx_atual,
                    key=f"status_{v['id']}"
                )

                if novo_status != status_vaga:
                    db.set_status(v["id"], novo_status)
                    st.rerun()

                if st.button(
                    "Marcar como Candidatada ✅",
                    key=f"btn_cand_{v['id']}"
                ):
                    db.set_status(v["id"], "candidatada")
                    st.rerun()

            with col_v2:
                notas_atuais = v.get("notes", "") or ""

                novas_notas = st.text_input(
                    "Minhas Anotações",
                    value=notas_atuais,
                    key=f"nota_{v['id']}"
                )

                if novas_notas != notas_atuais:
                    db.set_notes(v["id"], novas_notas)
                    st.toast("Anotação salva!")


# ==========================================
# ABA 3: CONFIGURAÇÕES E TESTES
# ==========================================
with aba_config:
    st.header("Configurações do Sistema")

    st.subheader("Testar Conexão com a IA")

    if st.button("Testar Chave da API"):
        with st.spinner("Testando conexão com a IA..."):
            try:
                sucesso, mensagem = llm.test_connection()

                if sucesso:
                    st.success(mensagem)
                else:
                    st.error(mensagem)

            except Exception as e:
                st.error(
                    f"Erro no teste da IA: {type(e).__name__}: {e}"
                )

    st.divider()

    st.subheader("Exportar Dados")

    if st.button("Preparar CSV com todas as vagas"):
        try:
            caminho_csv = "vagas_exportadas.csv"

            db.export_csv(caminho_csv)

            with open(caminho_csv, "rb") as arquivo:
                dados_csv = arquivo.read()

            st.download_button(
                label="Baixar minhas vagas em CSV",
                data=dados_csv,
                file_name="minhas_vagas.csv",
                mime="text/csv"
            )

            if os.path.exists(caminho_csv):
                os.remove(caminho_csv)

        except Exception as e:
            st.error(f"Erro ao exportar CSV: {e}")
