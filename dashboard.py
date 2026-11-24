import os
import json
import urllib.request

import streamlit as st
import db
import pipeline
import llm


# ==========================================
# CONFIGURAÇÃO
# ==========================================

st.set_page_config(
    page_title="Agente de Vagas",
    page_icon="🤖",
    layout="wide"
)

st.title("🤖 Agente de Vagas")
st.caption("Seu assistente pessoal de busca de oportunidades.")


# ==========================================
# ESTADOS E MUNICÍPIOS
# ==========================================

ESTADOS = {
    "Acre": "AC",
    "Alagoas": "AL",
    "Amapá": "AP",
    "Amazonas": "AM",
    "Bahia": "BA",
    "Ceará": "CE",
    "Distrito Federal": "DF",
    "Espírito Santo": "ES",
    "Goiás": "GO",
    "Maranhão": "MA",
    "Mato Grosso": "MT",
    "Mato Grosso do Sul": "MS",
    "Minas Gerais": "MG",
    "Pará": "PA",
    "Paraíba": "PB",
    "Paraná": "PR",
    "Pernambuco": "PE",
    "Piauí": "PI",
    "Rio de Janeiro": "RJ",
    "Rio Grande do Norte": "RN",
    "Rio Grande do Sul": "RS",
    "Rondônia": "RO",
    "Roraima": "RR",
    "Santa Catarina": "SC",
    "São Paulo": "SP",
    "Sergipe": "SE",
    "Tocantins": "TO"
}


@st.cache_data(ttl=86400, show_spinner=False)
def carregar_municipios(uf):
    """Carrega os municípios pela API oficial do IBGE."""

    if not uf:
        return []

    url = (
        "https://servicodados.ibge.gov.br/api/v1/"
        f"localidades/estados/{uf}/municipios"
    )

    try:
        requisicao = urllib.request.Request(
            url,
            headers={"User-Agent": "AgenteDeVagas/1.0"}
        )

        with urllib.request.urlopen(
            requisicao,
            timeout=15
        ) as resposta:
            dados = json.loads(
                resposta.read().decode("utf-8")
            )

        return sorted(
            [item["nome"] for item in dados],
            key=str.casefold
        )

    except Exception:
        return []


def selecionar_localizacao(prefixo):
    """Cria seletores dependentes de estado e cidade."""

    estado_opcoes = ["Todos"] + list(ESTADOS.keys())

    estado = st.selectbox(
        "Estado",
        estado_opcoes,
        key=f"{prefixo}_estado"
    )

    uf = ESTADOS.get(estado)

    cidades = carregar_municipios(uf) if uf else []

    if estado == "Todos":
        cidade_opcoes = ["Todas"]
        ajuda = "Selecione um estado para escolher uma cidade."

    elif not cidades:
        cidade_opcoes = ["Todas"]
        ajuda = (
            "Não foi possível carregar os municípios. "
            "Verifique sua conexão e tente novamente."
        )

    else:
        cidade_opcoes = ["Todas"] + cidades
        ajuda = "Escolha uma cidade ou mantenha Todas."

    cidade = st.selectbox(
        "Cidade",
        cidade_opcoes,
        key=f"{prefixo}_cidade",
        disabled=(estado == "Todos" or not cidades),
        help=ajuda
    )

    return (
        "" if estado == "Todos" else estado,
        "" if cidade == "Todas" else cidade
    )


# ==========================================
# FUNÇÕES AUXILIARES
# ==========================================

def mostrar_erro(titulo, erro):
    st.error(
        f"{titulo}: {type(erro).__name__}: {erro}"
    )


def carregar_perfil():
    try:
        return db.get_profile() or {}
    except Exception as erro:
        mostrar_erro("Erro ao carregar perfil", erro)
        return {}


def normalizar(texto):
    return str(texto or "").strip().casefold()


def vaga_corresponde_local(vaga, estado, cidade):
    """Verifica se a localização da vaga corresponde aos filtros."""

    local = normalizar(vaga.get("location", ""))

    if estado:
        uf = ESTADOS.get(estado, "").casefold()

        if (
            normalizar(estado) not in local
            and uf not in local.split()
            and f"/{uf}" not in local
            and f"-{uf}" not in local
        ):
            return False

    if cidade and normalizar(cidade) not in local:
        return False

    return True


# ==========================================
# NAVEGAÇÃO
# ==========================================

pagina = st.selectbox(
    "Navegação",
    [
        "📊 Painel de Vagas",
        "👤 Meu Perfil",
        "⚙️ Configurações"
    ],
    key="navegacao_principal"
)


# ==========================================
# PÁGINA: MEU PERFIL
# ==========================================

if pagina == "👤 Meu Perfil":

    st.header("👤 Meu Perfil")
    perfil = carregar_perfil()

    with st.form("form_perfil"):

        st.subheader("Dados pessoais")

        nome = st.text_input(
            "Nome completo",
            value=perfil.get("nome", "")
        )

        localizacao = st.text_input(
            "Cidade/UF",
            value=perfil.get("localizacao", "")
        )

        salario = st.text_input(
            "Salário mínimo desejado",
            value=perfil.get("salario_minimo", "")
        )

        modelos = [
            "Remoto",
            "Híbrido",
            "Presencial",
            "Indiferente"
        ]

        modelo_salvo = perfil.get(
            "modelo_trabalho",
            "Remoto"
        )

        indice = (
            modelos.index(modelo_salvo)
            if modelo_salvo in modelos
            else 0
        )

        modelo_trabalho = st.selectbox(
            "Modelo de trabalho preferido",
            modelos,
            index=indice
        )

        cidades = st.text_area(
            "Cidades que aceita",
            value=perfil.get("cidades_aceitas_txt", "")
        )

        cargos_nao = st.text_area(
            "Cargos que não deseja",
            value=perfil.get("cargos_nao_txt", "")
        )

        st.divider()
        st.subheader("Resumo profissional")

        resumo = st.text_area(
            "Resumo",
            value=perfil.get("resumo", ""),
            height=130
        )

        st.subheader("Habilidades")

        habilidades = st.text_area(
            "Habilidades e conhecimentos",
            value=perfil.get("habilidades_txt", ""),
            height=120
        )

        formacao = st.text_area(
            "Formação e cursos",
            value=perfil.get("formacao", ""),
            height=100
        )

        st.subheader("Experiências profissionais")

        experiencias = st.text_area(
            "Experiências",
            value=perfil.get("experiencias_txt", ""),
            height=180
        )

        st.subheader("Estilo de escrita")

        exemplos = st.text_area(
            "Exemplos de textos escritos por você",
            value=perfil.get("exemplos_escrita_txt", ""),
            height=150
        )

        salvar_perfil = st.form_submit_button(
            "💾 Salvar Perfil",
            use_container_width=True,
            type="primary"
        )

    if salvar_perfil:

        dados = {
            "nome": nome,
            "localizacao": localizacao,
            "salario_minimo": salario,
            "modelo_trabalho": modelo_trabalho,
            "cidades_aceitas_txt": cidades,
            "cargos_nao_txt": cargos_nao,
            "resumo": resumo,
            "habilidades_txt": habilidades,
            "formacao": formacao,
            "experiencias_txt": experiencias,
            "exemplos_escrita_txt": exemplos
        }

        try:
            db.save_profile(dados)
            st.success("Perfil salvo com sucesso!")

        except Exception as erro:
            mostrar_erro(
                "Não foi possível salvar o perfil",
                erro
            )


# ==========================================
# PÁGINA: CONFIGURAÇÕES
# ==========================================

elif pagina == "⚙️ Configurações":

    st.header("⚙️ Configurações")

    st.subheader("Adicionar site de vagas")

    with st.form("form_add_site"):

        nome_site = st.text_input(
            "Nome da empresa"
        )

        url_site = st.text_input(
            "URL da página de carreiras"
        )

        usa_js = st.checkbox(
            "O site utiliza JavaScript para carregar vagas (ex.: Gupy)"
        )

        adicionar = st.form_submit_button(
            "Adicionar site",
            use_container_width=True
        )

    if adicionar:

        if not url_site.strip().startswith(
            ("http://", "https://")
        ):
            st.error(
                "Informe uma URL válida começando com http:// ou https://"
            )

        else:
            try:
                db.add_source(
                    nome_site.strip() or url_site.strip(),
                    url_site.strip(),
                    usa_js
                )

                st.success(
                    "Site cadastrado com sucesso!"
                )

            except Exception as erro:
                mostrar_erro(
                    "Erro ao adicionar site",
                    erro
                )

    st.divider()
    st.subheader("Sites monitorados")

    try:
        sites = db.list_sources() or []

        if not sites:
            st.info("Nenhum site cadastrado.")

        for site in sites:

            with st.container(border=True):

                st.write(
                    f"**{site.get('name', 'Site')}**"
                )

                st.caption(
                    site.get("url", "")
                )

                if st.button(
                    "🗑️ Remover site",
                    key=f"remover_site_{site['id']}",
                    use_container_width=True
                ):

                    try:
                        db.remove_source(site["id"])

                        st.success(
                            "Site removido. Atualize a página para conferir."
                        )

                    except Exception as erro:
                        mostrar_erro(
                            "Erro ao remover site",
                            erro
                        )

    except Exception as erro:
        mostrar_erro(
            "Erro ao carregar sites",
            erro
        )

    st.divider()
    st.subheader("Conexão com inteligência artificial")

    if st.button(
        "🧪 Testar conexão com IA",
        use_container_width=True
    ):

        try:
            with st.spinner("Testando conexão..."):
                sucesso, mensagem = llm.test_connection()

            if sucesso:
                st.success(mensagem)
            else:
                st.error(mensagem)

        except Exception as erro:
            mostrar_erro(
                "Falha no teste da IA",
                erro
            )

    st.divider()
    st.subheader("Exportar dados")

    if st.button(
        "Preparar arquivo CSV",
        use_container_width=True
    ):

        try:
            caminho = "vagas_exportadas.csv"
            db.export_csv(caminho)

            with open(caminho, "rb") as arquivo:
                dados_csv = arquivo.read()

            st.download_button(
                "⬇️ Baixar minhas vagas",
                data=dados_csv,
                file_name="minhas_vagas.csv",
                mime="text/csv",
                use_container_width=True
            )

            if os.path.exists(caminho):
                os.remove(caminho)

        except Exception as erro:
            mostrar_erro(
                "Erro ao exportar CSV",
                erro
            )


# ==========================================
# PÁGINA: PAINEL DE VAGAS
# ==========================================

elif pagina == "📊 Painel de Vagas":

    st.header("📊 Painel de Vagas")

    # --------------------------------------
    # EXECUTAR BUSCA
    # --------------------------------------

    st.subheader("Busca de oportunidades")

    st.write(
        "Escolha onde o agente deve procurar novas oportunidades."
    )

    estado_busca, cidade_busca = selecionar_localizacao(
        "busca"
    )

    if st.button(
        "🚀 Buscar vagas agora",
        type="primary",
        use_container_width=True
    ):

        linhas_log = []

        def registrar_log(mensagem):
            linhas_log.append(str(mensagem))

        filtros = {
            "estado": estado_busca,
            "cidade": cidade_busca
        }

        try:
            with st.spinner(
                "O agente está procurando e analisando vagas. Aguarde..."
            ):

                resultado = pipeline.run_once(
                    log=registrar_log,
                    filtros=filtros
                )

            st.success("Busca finalizada!")

            col1, col2, col3 = st.columns(3)

            with col1:
                st.metric(
                    "Encontradas",
                    resultado.get("encontradas", 0)
                )

                st.metric(
                    "Analisadas",
                    resultado.get("analisadas", 0)
                )

            with col2:
                st.metric(
                    "Boas oportunidades",
                    resultado.get("para_avaliar", 0)
                )

                st.metric(
                    "Descartadas",
                    resultado.get("descartadas", 0)
                )

            with col3:
                st.metric(
                    "Ignoradas",
                    resultado.get("ignoradas", 0)
                )

                st.metric(
                    "Erros",
                    resultado.get("erros", 0)
                )

        except Exception as erro:
            mostrar_erro(
                "Falha durante a busca",
                erro
            )

        if linhas_log:

            with st.expander(
                "📋 Ver registro da busca",
                expanded=True
            ):

                st.code(
                    "\n".join(linhas_log[-100:]),
                    language="text"
                )

    st.divider()

    # --------------------------------------
    # MÉTRICAS DAS CANDIDATURAS
    # --------------------------------------

    st.subheader("Resumo das candidaturas")

    try:
        contagens = db.counts() or {}

    except Exception as erro:
        contagens = {}

        mostrar_erro(
            "Erro ao consultar métricas",
            erro
        )

    metricas = [
        ("Analisadas", contagens.get("total", 0)),
        ("Para avaliar", contagens.get("para_avaliar", 0)),
        ("Candidatadas", contagens.get("candidatada", 0)),
        ("Em processo", contagens.get("em_processo", 0)),
        ("Descartadas", contagens.get("descartada", 0))
    ]

    # Bloco corrigido: indentação uniforme.
    for inicio in range(0, len(metricas), 2):

        colunas = st.columns(2)

        itens_linha = metricas[inicio:inicio + 2]

        for coluna, item in zip(colunas, itens_linha):

            with coluna:
                st.metric(
                    item[0],
                    item[1]
                )

    st.divider()

    # --------------------------------------
    # FILTROS DAS VAGAS SALVAS
    # --------------------------------------

    st.subheader("Minhas vagas")

    filtro_status = st.selectbox(
        "Filtrar por status",
        [
            "Todas",
            "para_avaliar",
            "candidatada",
            "em_processo",
            "pendente",
            "descartada"
        ],
        key="filtro_status"
    )

    filtro_busca = st.text_input(
        "Buscar por empresa ou cargo",
        key="filtro_texto"
    )

    filtro_nota = st.slider(
        "Nota mínima",
        min_value=0,
        max_value=100,
        value=0,
        key="filtro_nota"
    )

    st.write("Filtrar vagas por localização:")

    estado_lista, cidade_lista = selecionar_localizacao(
        "lista"
    )

    # --------------------------------------
    # CARREGAR VAGAS
    # --------------------------------------

    try:
        vagas = db.list_jobs() or []

    except Exception as erro:
        vagas = []

        mostrar_erro(
            "Erro ao carregar vagas",
            erro
        )

    vagas_filtradas = []

    for vaga in vagas:

        if (
            filtro_status != "Todas"
            and vaga.get("status") != filtro_status
        ):
            continue

        if (vaga.get("score") or 0) < filtro_nota:
            continue

        if filtro_busca:

            termo = normalizar(filtro_busca)

            titulo_vaga = normalizar(
                vaga.get("title", "")
            )

            empresa_vaga = normalizar(
                vaga.get("company", "")
            )

            if (
                termo not in titulo_vaga
                and termo not in empresa_vaga
            ):
                continue

        if not vaga_corresponde_local(
            vaga,
            estado_lista,
            cidade_lista
        ):
            continue

        vagas_filtradas.append(vaga)

    st.caption(
        f"{len(vagas_filtradas)} oportunidade(s) encontrada(s)."
    )

    if not vagas_filtradas:
        st.info(
            "Nenhuma vaga encontrada. Execute uma busca ou altere os filtros."
        )

    # --------------------------------------
    # EXIBIR VAGAS
    # --------------------------------------

    for vaga in vagas_filtradas:

        score_vaga = vaga.get("score") or 0
        status = vaga.get("status", "")

        icone = (
            "🟢" if score_vaga >= 65
            else "🔴" if status == "descartada"
            else "🟡"
        )

        titulo = (
            f"{icone} Nota {score_vaga} | "
            f"{vaga.get('title', 'Sem título')}"
        )

        with st.expander(titulo):

            st.write(
                f"**Empresa:** {vaga.get('company', 'Não informada')}"
            )

            url = vaga.get("url", "")

            if url:
                st.markdown(
                    f"[🔗 Abrir vaga]({url})"
                )

            st.write(
                f"**Local:** {vaga.get('location', '')}"
            )

            st.write(
                f"**Fonte:** {vaga.get('source', '')}"
            )

            st.write(
                f"**Encontrada em:** "
                f"{str(vaga.get('found_at', ''))[:10]}"
            )

            st.info(
                f"**Justificativa da IA:** "
                f"{vaga.get('reason', '')}"
            )

            if status == "descartada":

                st.error(
                    f"**Motivo do descarte:** "
                    f"{vaga.get('discard_reason', '')}"
                )

            carta = vaga.get("cover_letter")

            if carta:

                st.warning(
                    "Revise a carta antes de utilizar."
                )

                st.text_area(
                    "Carta de apresentação sugerida",
                    value=carta,
                    height=180,
                    key=f"carta_{vaga['id']}"
                )

            st.divider()

            # Formulário individual para cada vaga.
            with st.form(
                f"form_vaga_{vaga['id']}"
            ):

                opcoes_status = [
                    "para_avaliar",
                    "candidatada",
                    "em_processo",
                    "pendente",
                    "descartada"
                ]

                indice_status = (
                    opcoes_status.index(status)
                    if status in opcoes_status
                    else 0
                )

                novo_status = st.selectbox(
                    "Status da candidatura",
                    opcoes_status,
                    index=indice_status
                )

                novas_notas = st.text_area(
                    "Minhas anotações",
                    value=vaga.get("notes", "") or "",
                    height=90
                )

                salvar_alteracoes = st.form_submit_button(
                    "💾 Salvar alterações",
                    use_container_width=True
                )

           ência artificial")

    if st.button(
        "🧪 Testar conexão com IA",
        use_container_width=True
    ):

        try:
            with st.spinner("Testando conexão..."):
                sucesso, mensagem = llm.test_connection()

            if sucesso:
                st.success(mensagem)
            else:
                st.error(mensagem)

        except Exception as erro:
            mostrar_erro(
                "Falha no teste da IA",
                erro
            )

    st.divider()
    st.subheader("Exportar dados")

    if st.button(
        "Preparar arquivo CSV",
        use_container_width=True
    ):

        try:
            caminho = "vagas_exportadas.csv"
            db.export_csv(caminho)

            with open(caminho, "rb") as arquivo:
                dados_csv = arquivo.read()

            st.download_button(
                "⬇️ Baixar minhas vagas",
                data=dados_csv,
                file_name="minhas_vagas.csv",
                mime="text/csv",
                use_container_width=True
            )

            if os.path.exists(caminho):
                os.remove(caminho)

        except Exception as erro:
            mostrar_erro(
                "Erro ao exportar CSV",
                erro
            )


# ==========================================
# PÁGINA: PAINEL DE VAGAS
# ==========================================

elif pagina == "📊 Painel de Vagas":

    st.header("📊 Painel de Vagas")

    # --------------------------------------
    # EXECUTAR BUSCA
    # --------------------------------------

    st.subheader("Busca de oportunidades")

    st.write(
        "Escolha onde o agente deve procurar novas oportunidades."
    )

    estado_busca, cidade_busca = selecionar_localizacao(
        "busca"
    )

    if st.button(
        "🚀 Buscar vagas agora",
        type="primary",
        use_container_width=True
    ):

        linhas_log = []

        def registrar_log(mensagem):
            linhas_log.append(str(mensagem))

        filtros = {
            "estado": estado_busca,
            "cidade": cidade_busca
        }

        try:
            with st.spinner(
                "O agente está procurando e analisando vagas. Aguarde..."
            ):

                resultado = pipeline.run_once(
                    log=registrar_log,
                    filtros=filtros
                )

            st.success("Busca finalizada!")

            col1, col2, col3 = st.columns(3)

            with col1:
                st.metric(
                    "Encontradas",
                    resultado.get("encontradas", 0)
                )

                st.metric(
                    "Analisadas",
                    resultado.get("analisadas", 0)
                )

            with col2:
                st.metric(
                    "Boas oportunidades",
                    resultado.get("para_avaliar", 0)
                )

                st.metric(
                    "Descartadas",
                    resultado.get("descartadas", 0)
                )

            with col3:
                st.metric(
                    "Ignoradas",
                    resultado.get("ignoradas", 0)
                )

                st.metric(
                    "Erros",
                    resultado.get("erros", 0)
                )

        except Exception as erro:
            mostrar_erro(
                "Falha durante a busca",
                erro
            )

        if linhas_log:

            with st.expander(
                "📋 Ver registro da busca",
                expanded=True
            ):

                st.code(
                    "\n".join(linhas_log[-100:]),
                    language="text"
                )

    st.divider()

    # --------------------------------------
    # MÉTRICAS
    # --------------------------------------

    st.subheader("Resumo das candidaturas")

    try:
        contagens = db.counts() or {}

    except Exception as erro:
        contagens = {}

        mostrar_erro(
            "Erro ao consultar métricas",
            erro
        )

    metricas = [
        ("Analisadas", contagens.get("total", 0)),
        ("Para avaliar", contagens.get("para_avaliar", 0)),
        ("Candidatadas", contagens.get("candidatada", 0)),
        ("Em processo", contagens.get("em_processo", 0)),
        ("Descartadas", contagens.get("descartada", 0))
    ]

    for inicio in range(0, len(metricas), 2):

        colunas = st.columns(2)

        for coluna, item in zip(
            colunas,
            metricas[inicio:inicio + 2]
        ):

            with coluna:
                st.metric(
                    item[0],
                    item[1]
                )

    st.divider()

    # --------------------------------------
    # FILTROS DAS VAGAS SALVAS
    # --------------------------------------

    st.subheader("Minhas vagas")

    filtro_status = st.selectbox(
        "Filtrar por status",
        [
            "Todas",
            "para_avaliar",
            "candidatada",
            "em_processo",
            "pendente",
            "descartada"
        ],
        key="filtro_status"
    )

    filtro_busca = st.text_input(
        "Buscar por empresa ou cargo",
        key="filtro_texto"
    )

    filtro_nota = st.slider(
        "Nota mínima",
        min_value=0,
        max_value=100,
        value=0,
        key="filtro_nota"
    )

    st.write("Filtrar vagas por localização:")

    estado_lista, cidade_lista = selecionar_localizacao(
        "lista"
    )

    # --------------------------------------
    # CARREGAR VAGAS
    # --------------------------------------

    try:
        vagas = db.list_jobs() or []

    except Exception as erro:
        vagas = []

        mostrar_erro(
            "Erro ao carregar vagas",
            erro
        )

    vagas_filtradas = []

    for vaga in vagas:

        if (
            filtro_status != "Todas"
            and vaga.get("status") != filtro_status
        ):
            continue

        if (vaga.get("score") or 0) < filtro_nota:
            continue

        if filtro_busca:

            termo = normalizar(filtro_busca)

            titulo = normalizar(
                vaga.get("title", "")
            )

            empresa = normalizar(
                vaga.get("company", "")
            )

            if termo not in titulo and termo not in empresa:
                continue

        if not vaga_corresponde_local(
            vaga,
            estado_lista,
            cidade_lista
        ):
            continue

        vagas_filtradas.append(vaga)

    st.caption(
        f"{len(vagas_filtradas)} oportunidade(s) encontrada(s)."
    )

    if not vagas_filtradas:
        st.info(
            "Nenhuma vaga encontrada. Execute uma busca ou altere os filtros."
        )

    # --------------------------------------
    # EXIBIR VAGAS
    # --------------------------------------

    for vaga in vagas_filtradas:

        score = vaga.get("score") or 0
        status = vaga.get("status", "")

        icone = (
            "🟢" if score >= 65
            else "🔴" if status == "descartada"
            else "🟡"
        )

        titulo = (
            f"{icone} Nota {score} | "
            f"{vaga.get('title', 'Sem título')}"
        )

        with st.expander(titulo):

            st.write(
                f"**Empresa:** {vaga.get('company', 'Não informada')}"
            )

            url = vaga.get("url", "")

            if url:
                st.markdown(
                    f"[🔗 Abrir vaga]({url})"
                )

            st.write(
                f"**Local:** {vaga.get('location', '')}"
            )

            st.write(
                f"**Fonte:** {vaga.get('source', '')}"
            )

            st.write(
                f"**Encontrada em:** "
                f"{str(vaga.get('found_at', ''))[:10]}"
            )

            st.info(
                f"**Justificativa da IA:** "
                f"{vaga.get('reason', '')}"
            )

            if status == "descartada":

                st.error(
                    f"**Motivo do descarte:** "
                    f"{vaga.get('discard_reason', '')}"
                )

            carta = vaga.get("cover_letter")

            if carta:

                st.warning(
                    "Revise a carta antes de utilizar."
                )

                st.text_area(
                    "Carta de apresentação sugerida",
                    value=carta,
                    height=180,
                    key=f"carta_{vaga['id']}"
                )

            st.divider()

            with st.form(
                f"form_vaga_{vaga['id']}"
            ):

                opcoes_status = [
                    "para_avaliar",
                    "candidatada",
                    "em_processo",
                    "pendente",
                    "descartada"
                ]

                indice_status = (
                    opcoes_status.index(status)
                    if status in opcoes_status
                    else 0
                )

                novo_status = st.selectbox(
                    "Status da candidatura",
                    opcoes_status,
                    index=indice_status
                )

                novas_notas = st.text_area(
                    "Minhas anotações",
                    value=vaga.get("notes", "") or "",
                    height=90
                )

                salvar_alteracoes = st.form_submit_button(
                    "💾 Salvar alterações",
                    use_container_width=True
                )

            if salvar_alteracoes:

                try:
                    db.set_status(
                        vaga["id"],
                        novo_status
                    )

                    db.set_notes(
                        vaga["id"],
                        novas_notas
                    )
           metricas[inicio:inicio + 2]
        ):

            with coluna:
                st.metric(item[0], item[1])

    st.divider()

    # --------------------------------------
    # FILTROS
    # --------------------------------------

    st.subheader("Minhas vagas")

    filtro_status = st.selectbox(
        "Filtrar por status",
        [
            "Todas",
            "para_avaliar",
            "candidatada",
            "em_processo",
            "pendente",
            "descartada"
        ]
    )

    filtro_busca = st.text_input(
        "Buscar por empresa ou cargo"
    )

    filtro_nota = st.slider(
        "Nota mínima",
        min_value=0,
        max_value=100,
        value=0
    )

    # --------------------------------------
    # CARREGAR VAGAS
    # --------------------------------------

    try:
        vagas = db.list_jobs() or []

    except Exception as erro:
        vagas = []
        mostrar_erro("Erro ao carregar vagas", erro)

    vagas_filtradas = []

    for vaga in vagas:

        if (
            filtro_status != "Todas"
            and vaga.get("status") != filtro_status
        ):
            continue

        if (vaga.get("score") or 0) < filtro_nota:
            continue

        if filtro_busca:

            termo = filtro_busca.lower()

            titulo = str(vaga.get("title", "")).lower()
            empresa = str(vaga.get("company", "")).lower()

            if termo not in titulo and termo not in empresa:
                continue

        vagas_filtradas.append(vaga)

    st.caption(
        f"{len(vagas_filtradas)} oportunidade(s) encontrada(s)."
    )

    if not vagas_filtradas:
        st.info(
            "Nenhuma vaga encontrada. Execute uma busca ou altere os filtros."
        )

    # --------------------------------------
    # EXIBIR VAGAS
    # --------------------------------------

    for vaga in vagas_filtradas:

        score = vaga.get("score") or 0
        status = vaga.get("status", "")

        icone = (
            "🟢" if score >= 65
            else "🔴" if status == "descartada"
            else "🟡"
        )

        titulo = (
            f"{icone} Nota {score} | "
            f"{vaga.get('title', 'Sem título')}"
        )

        with st.expander(titulo):

            st.write(
                f"**Empresa:** {vaga.get('company', 'Não informada')}"
            )

            url = vaga.get("url", "")

            if url:
                st.markdown(f"[🔗 Abrir vaga]({url})")

            st.write(
                f"**Local:** {vaga.get('location', '')}"
            )

            st.write(
                f"**Fonte:** {vaga.get('source', '')}"
            )

            st.write(
                f"**Encontrada em:** {str(vaga.get('found_at', ''))[:10]}"
            )

            st.info(
                f"**Justificativa da IA:** {vaga.get('reason', '')}"
            )

            if status == "descartada":
                st.error(
                    f"**Motivo do descarte:** "
                    f"{vaga.get('discard_reason', '')}"
                )

            carta = vaga.get("cover_letter")

            if carta:

                st.warning(
                    "Revise a carta antes de utilizar."
                )

                st.text_area(
                    "Carta de apresentação sugerida",
                    value=carta,
                    height=180,
                    key=f"carta_{vaga['id']}"
                )

            st.divider()

            # Formulário individual para cada vaga.
            with st.form(f"form_vaga_{vaga['id']}"):

                opcoes_status = [
                    "para_avaliar",
                    "candidatada",
                    "em_processo",
                    "pendente",
                    "descartada"
                ]

                indice_status = (
                    opcoes_status.index(status)
                    if status in opcoes_status
                    else 0
                )

                novo_status = st.selectbox(
                    "Status da candidatura",
                    opcoes_status,
                    index=indice_status
                )

                novas_notas = st.text_area(
                    "Minhas anotações",
                    value=vaga.get("notes", "") or "",
                    height=90
                )

                salvar_alteracoes = st.form_submit_button(
                    "💾 Salvar alterações",
                    use_container_width=True
                )

            if salvar_alteracoes:

                try:
                    db.set_status(
                        vaga["id"],
                        novo_status
                    )

                    db.set_notes(
                        vaga["id"],
                        novas_notas
                    )

                    st.success(
                        "Alterações salvas! Atualize a página para visualizar os dados atualizados."
                    )

                except Exception as erro:
                    mostrar_erro(
                        "Erro ao salvar alterações",
                        erro
                    )
