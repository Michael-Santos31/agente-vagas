import streamlit as st
import pandas as pd
import time
import os
import io
import db
import pipeline
import llm

# Configuração da página (deve ser a primeira coisa a rodar)
st.set_page_config(page_title="Agente de Vagas", page_icon="🤖", layout="wide")

st.title("🤖 Candidaturas - Agente de Vagas")

# Cria as abas do painel
aba_vagas, aba_perfil, aba_config = st.tabs(["📊 Painel de Vagas", "👤 Meu Perfil", "⚙️ Configurações e Testes"])

# ==========================================
# ABA 2: MEU PERFIL (A que você pediu!)
# ==========================================
with aba_perfil:
    st.header("Meus Dados e Estilo de Escrita")
    st.info(
        "Preencha seus dados reais. A Inteligência Artificial usará essas informações para dar as notas e escrever as cartas.")

    # Carrega o perfil do banco de dados
    perfil_salvo = db.get_profile()

    with st.form("form_perfil"):
        col1, col2 = st.columns(2)
        with col1:
            nome = st.text_input("Seu Nome Completo", value=perfil_salvo.get("nome", ""))
            localizacao = st.text_input("Sua Localização (Cidade/UF)", value=perfil_salvo.get("localizacao", ""))
            salario = st.text_input("Salário Mínimo Desejado (Ex: R$ 3.500)",
                                    value=perfil_salvo.get("salario_minimo", ""))
        with col2:
            modelo_trabalho = st.selectbox("Modelo de Trabalho Preferido",
                                           ["Remoto", "Híbrido", "Presencial", "Indiferente"], index=0)
            cidades_aceitas = st.text_input("Cidades que aceita (se presencial/híbrido)",
                                            value=perfil_salvo.get("cidades_aceitas_txt", ""))
            cargos_nao = st.text_input("Cargos que você NÃO quer de jeito nenhum",
                                       value=perfil_salvo.get("cargos_nao_txt", ""))

        resumo = st.text_area("Resumo Profissional (3 a 5 linhas)", value=perfil_salvo.get("resumo", ""), height=100)

        st.subheader("Habilidades e Formação")
        habilidades_txt = st.text_area("Habilidades que você REALMENTE tem (separe por vírgula)",
                                       value=perfil_salvo.get("habilidades_txt", ""), height=80)
        formacao = st.text_area("Formação e Cursos", value=perfil_salvo.get("formacao", ""), height=80)

        st.subheader("Experiências")
        st.write("(Escreva uma por linha no formato: Cargo | Empresa | Período | O que fez)")
        experiencias_txt = st.text_area("Experiências Profissionais", value=perfil_salvo.get("experiencias_txt", ""),
                                        height=150)

        st.subheader("Meu Jeito de Escrever (Exemplos)")
        st.write("Cole de 2 a 3 cartas de apresentação antigas ou textos seus. A IA vai copiar o seu tom de voz.")
        exemplos = st.text_area("Textos de Exemplo", value=perfil_salvo.get("exemplos_escrita_txt", ""), height=200)

        botao_salvar_perfil = st.form_submit_button("💾 Salvar Perfil", type="primary")

        if botao_salvar_perfil:
            # Converte as listas separadas por vírgula/linha em listas reais
            dados_perfil = {
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
            db.save_profile(dados_perfil)
            st.success("Perfil salvo com sucesso! O robô já pode usar essas informações.")
            time.sleep(1.5)
            st.rerun()

# ==========================================
# ABA 1: PAINEL DE VAGAS
# ==========================================
with aba_vagas:
    # --- BARRA LATERAL ---
    with st.sidebar:
        st.header("Ações do Agente")

        # Botão de Buscar
        if st.button("🚀 Buscar vagas agora", use_container_width=True, type="primary"):
            with st.spinner("O robô está trabalhando. Isso pode levar alguns minutos..."):
                log_placeholder = st.empty()


                def escrever_log(msg):
                    log_placeholder.code(msg, language="text")


                stats = pipeline.run_once(log=escrever_log)
                st.success(f"Rodada finalizada! Analisadas: {stats['analisadas']} | Boas: {stats['para_avaliar']}")
                time.sleep(2)
                st.rerun()

        st.divider()

        # Adicionar Site
        st.subheader("Adicionar Site de Vagas")
        with st.form("form_add_site"):
            nome_site = st.text_input("Nome da Empresa/Site")
            url_site = st.text_input("URL da Página de Carreiras")
            usa_js = st.checkbox("O site carrega vagas com JavaScript (ex: Gupy)")
            add_btn = st.form_submit_button("Adicionar Site")

            if add_btn:
                if url_site.startswith("http"):
                    db.add_source(nome_site, url_site, usa_js)
                    st.success("Site adicionado!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("A URL deve começar com http:// ou https://")

        # Listar Sites
        st.subheader("Sites Monitorados")
        sites = db.list_sources()
        if not sites:
            st.info("Nenhum site cadastrado.")
        for s in sites:
            col_s1, col_s2 = st.columns([3, 1])
            with col_s1:
                st.caption(f"**{s['name']}**\n{s['url']}")
            with col_s2:
                if st.button("🗑️", key=f"del_{s['id']}"):
                    db.remove_source(s['id'])
                    st.rerun()
            st.divider()

    # --- CONTEÚDO PRINCIPAL DA ABA DE VAGAS ---

    # Cartões de Métricas
    contagens = db.counts()
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Analisadas", contagens.get('total', 0))
    c2.metric("Para Avaliar", contagens.get('para_avaliar', 0))
    c3.metric("Candidatadas", contagens.get('candidatada', 0))
    c4.metric("Em Processo", contagens.get('em_processo', 0))
    c5.metric("Descartadas", contagens.get('descartada', 0))

    st.divider()

    # Filtros
    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        filtro_status = st.selectbox("Filtrar por Status",
                                     ["Todas", "para_avaliar", "candidatada", "em_processo", "pendente", "descartada"])
    with col_f2:
        filtro_busca = st.text_input("Buscar empresa ou cargo")
    with col_f3:
        filtro_nota = st.slider("Nota mínima", 0, 100, 0)

    # Listar Vagas
    vagas = db.list_jobs()

    # Aplica filtros
    vagas_filtradas = []
    for v in vagas:
        if filtro_status != "Todas" and v['status'] != filtro_status:
            continue
        if filtro_nota > 0 and (v['score'] or 0) < filtro_nota:
            continue
        if filtro_busca:
            busca_lower = filtro_busca.lower()
            titulo = str(v.get('title', '')).lower()
            empresa = str(v.get('company', '')).lower()
            if busca_lower not in titulo and busca_lower not in empresa:
                continue
        vagas_filtradas.append(v)

    if not vagas_filtradas:
        st.info("Nenhuma vaga aqui ainda. Adicione um site na barra lateral e clique em Buscar vagas agora.")

    for v in vagas_filtradas:
        # Cabeçalho da vaga
        icone = "🟢" if (v['score'] or 0) >= 65 else "🔴" if v['status'] == 'descartada' else "🟡"
        titulo_expander = f"{icone} Nota {v['score']} | {v['title']} - {v['company']}"

        with st.expander(titulo_expander):
            st.markdown(f"**Link:** [Abrir Vaga]({v['url']})")
            st.markdown(
                f"**Local:** {v['location']} | **Fonte:** {v['source']} | **Encontrada em:** {v['found_at'][:10]}")

            st.info(f"**Justificativa da IA:** {v['reason']}")

            if v['status'] == 'descartada':
                st.error(f"**Motivo do Descarte:** {v['discard_reason']}")

            if v['cover_letter']:
                st.warning("⚠️ **Revise antes de usar. A IA pode cometer erros.**")
                if "[REVISAR:" in v['cover_letter']:
                    st.error("A IA gerou um alerta nesta carta. Verifique se ela inventou alguma informação.")
                st.text_area("Carta Sugerida", value=v['cover_letter'], height=200, key=f"carta_{v['id']}")

            # Controles de Status e Anotações
            col_v1, col_v2 = st.columns([1, 2])
            with col_v1:
                # Lista de status possíveis
                opcoes_status = ["para_avaliar", "candidatada", "em_processo", "pendente", "descartada"]
                idx_atual = opcoes_status.index(v['status']) if v['status'] in opcoes_status else 0

                novo_status = st.selectbox("Status", opcoes_status, index=idx_atual, key=f"status_{v['id']}")
                if novo_status != v['status']:
                    db.set_status(v['id'], novo_status)
                    st.rerun()

                if st.button("Marcar como Candidatada ✅", key=f"btn_cand_{v['id']}"):
                    db.set_status(v['id'], "candidatada")
                    st.rerun()

            with col_v2:
                notas_atuais = v.get('notes', '') or ''
                novas_notas = st.text_input("Minhas Anotações", value=notas_atuais, key=f"nota_{v['id']}")
                if novas_notas != notas_atuais:
                    db.set_notes(v['id'], novas_notas)
                    st.toast("Anotação salva!")

# ==========================================
# ABA 3: CONFIGURAÇÕES E TESTES
# ==========================================
with aba_config:
    st.header("Configurações do Sistema")

    st.subheader("Testar Conexão com a IA (DeepSeek)")
    if st.button("Testar Chave da API"):
        with st.spinner("Conectando ao DeepSeek..."):
            sucesso, mensagem = llm.test_connection()
            if sucesso:
                st.success(mensagem)
            else:
                st.error(mensagem)

    st.divider()
    st.subheader("Exportar Dados")
    if st.button("Baixar todas as vagas em CSV"):
        caminho_csv = "vagas_exportadas.csv"
        db.export_csv(caminho_csv)
        with open(caminho_csv, "r", encoding="utf-8") as f:
            st.download_button(
                label="Clique aqui para baixar o CSV",
                data=f,
                file_name="minhas_vagas.csv",
                mime="text/csv"
            )
        os.remove(caminho_csv)  # Limpa o arquivo do servidor após gerar