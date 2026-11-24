"""Avaliação de vagas e geração de cartas com o perfil salvo no painel."""

import json
import re

import llm


def _lista(valor):
    """Converte texto ou lista em uma lista limpa de strings."""
    if valor is None:
        return []
    if isinstance(valor, list):
        return [str(item).strip() for item in valor if str(item).strip()]
    return [
        item.strip()
        for item in re.split(r"[,;\n]+", str(valor))
        if item.strip()
    ]


def _experiencias(perfil):
    """Aceita tanto experiências estruturadas quanto o texto do formulário."""
    experiencias = perfil.get("experiencias", [])
    if isinstance(experiencias, list) and experiencias:
        resultado = []
        for exp in experiencias:
            if isinstance(exp, dict):
                partes = [
                    exp.get("cargo", ""),
                    exp.get("empresa", ""),
                    exp.get("periodo", ""),
                    exp.get("descricao", ""),
                ]
                texto = " | ".join(str(p).strip() for p in partes if p)
                if texto:
                    resultado.append(texto)
            elif str(exp).strip():
                resultado.append(str(exp).strip())
        return resultado

    texto = perfil.get("experiencias_txt", "")
    resultado = []
    for linha in str(texto).splitlines():
        linha = linha.strip()
        if not linha:
            continue
        partes = [p.strip() for p in linha.split("|")]
        if len(partes) >= 2:
            rotulos = ["Cargo", "Empresa", "Período", "Atividades"]
            resultado.append(
                " | ".join(
                    f"{rotulos[i]}: {parte}"
                    for i, parte in enumerate(partes[:4])
                    if parte
                )
            )
        else:
            resultado.append(linha)
    return resultado


def _texto_formacao(perfil):
    valor = perfil.get("formacao", "")
    if isinstance(valor, list):
        return "\n".join(f"- {str(item).strip()}" for item in valor if str(item).strip())
    return str(valor).strip()


def formatar_perfil_para_ia(profile_dict):
    """Transforma os campos atuais e antigos do painel em texto para a IA."""
    perfil = profile_dict or {}

    habilidades = _lista(
        perfil.get("habilidades", perfil.get("habilidades_txt", ""))
    )
    cidades = _lista(
        perfil.get("cidades_aceitas", perfil.get("cidades_aceitas_txt", ""))
    )
    cargos_nao = _lista(
        perfil.get("cargos_nao_desejados", perfil.get("cargos_nao_txt", ""))
    )
    cargos_desejados = _lista(perfil.get("cargos_desejados", []))
    experiencias = _experiencias(perfil)

    exemplos = perfil.get(
        "exemplos_escrita",
        perfil.get("exemplos_escrita_txt", "")
    )
    if isinstance(exemplos, list):
        exemplos_texto = "\n\n".join(
            str(item).strip() for item in exemplos if str(item).strip()
        )
    else:
        exemplos_texto = str(exemplos or "").strip()

    linhas = [
        "--- DADOS DO CANDIDATO ---",
        f"Nome: {perfil.get('nome', 'Não informado')}",
        f"Localização: {perfil.get('localizacao', 'Não informada')}",
        f"Resumo profissional: {perfil.get('resumo', '')}",
        "",
        "EXPERIÊNCIAS PROFISSIONAIS:",
    ]

    linhas.extend(f"- {item}" for item in experiencias)
    if not experiencias:
        linhas.append("- Não informado")

    linhas.extend(["", "FORMAÇÃO E CURSOS:", _texto_formacao(perfil) or "- Não informado"])
    linhas.extend(["", "HABILIDADES INFORMADAS:"])
    linhas.extend(f"- {item}" for item in habilidades)
    if not habilidades:
        linhas.append("- Não informado")

    linhas.extend([
        "",
        "PREFERÊNCIAS DE TRABALHO:",
        f"Cargos desejados: {', '.join(cargos_desejados) or 'Não especificados'}",
        f"Cargos não desejados: {', '.join(cargos_nao) or 'Não especificados'}",
        f"Modelo de trabalho: {perfil.get('modelo_trabalho', 'Não informado')}",
        f"Cidades aceitas: {', '.join(cidades) or 'Não especificadas'}",
        f"Salário mínimo desejado: {perfil.get('salario_minimo', 'Não informado')}",
        "",
        "EXEMPLOS DO JEITO DE ESCREVER DO CANDIDATO:",
        exemplos_texto or "Nenhum exemplo fornecido.",
    ])

    return "\n".join(linhas)


def _extrair_json(texto):
    """Extrai e valida o objeto JSON retornado pelo modelo."""
    match = re.search(r"\{.*\}", texto, re.DOTALL)
    if not match:
        raise ValueError("A resposta da IA não contém um objeto JSON.")
    resultado = json.loads(match.group(0))
    if not isinstance(resultado, dict):
        raise ValueError("A resposta da IA não é um objeto JSON.")
    return resultado


def evaluate(job_text, url, profile_dict):
    """Avalia a compatibilidade de uma vaga com o perfil do candidato."""
    perfil_txt = formatar_perfil_para_ia(profile_dict)

    system_prompt = """Você é um avaliador rigoroso de vagas de emprego.
Responda SOMENTE com um objeto JSON válido, sem Markdown, neste formato:
{
  "is_job_posting": true,
  "title": "título da vaga",
  "company": "nome da empresa",
  "location": "localização",
  "score": 0,
  "reason": "justificativa objetiva",
  "discard_reason": "",
  "missing_requirements": []
}

Regras:
1. Se o conteúdo não for uma vaga específica, use is_job_posting=false e score=0.
2. Avalie compatibilidade real considerando experiências, habilidades, formação,
localização, modelo de trabalho, salário e senioridade informados.
3. Não presuma que o candidato possui habilidades ou experiências não listadas.
4. Se exigir requisito obrigatório ausente, reduza a nota e informe-o em
missing_requirements.
5. Cargo explicitamente não desejado ou salário abaixo do mínimo informado
deve reduzir bastante a nota.
6. Se salário não estiver publicado, não penalize por isso; mencione a ausência.
7. Não invente informações sobre a vaga ou sobre o candidato.
8. score deve ser um número inteiro de 0 a 100."""

    user_prompt = (
        f"AVALIE A SEGUINTE VAGA:\nURL: {url}\n\n"
        f"TEXTO DA VAGA:\n{job_text}\n\n{perfil_txt}"
    )

    try:
        resposta = llm.ask(system_prompt, user_prompt, max_tokens=1000)
        resultado = _extrair_json(resposta)
        resultado["score"] = max(0, min(100, int(resultado.get("score", 0))))
        resultado["is_job_posting"] = bool(resultado.get("is_job_posting", False))
        resultado.setdefault("title", "Título não identificado")
        resultado.setdefault("company", "Empresa não identificada")
        resultado.setdefault("location", "Não informada")
        resultado.setdefault("reason", "Sem justificativa.")
        resultado.setdefault("discard_reason", "")
        requisitos = resultado.get("missing_requirements", [])
        resultado["missing_requirements"] = (
            requisitos if isinstance(requisitos, list) else [str(requisitos)]
        )
        return resultado
    except Exception as erro:
        print(f"Erro ao avaliar vaga: {erro}")
        return None


def write_letter(job_text, job, profile_dict):
    """Gera uma carta curta, usando apenas informações presentes no perfil."""
    perfil_txt = formatar_perfil_para_ia(profile_dict)

    system_prompt = """Você escreve cartas de apresentação em português do Brasil,
na voz do candidato descrito no perfil.
Escreva entre 120 e 180 palavras, com tom natural, profissional e direto.
Use somente fatos presentes no perfil. Não invente habilidades, resultados,
números, empresas, cursos ou experiências. Relacione a experiência real do
candidato a pontos concretos da vaga. Se não houver informação suficiente,
seja transparente e não preencha lacunas com suposições.
Imite o estilo dos exemplos fornecidos, se existirem.
Retorne somente o texto da carta."""

    user_prompt = (
        f"VAGA:\nCargo: {job.get('title', '')}\n"
        f"Empresa: {job.get('company', '')}\n"
        f"Descrição:\n{job_text}\n\n{perfil_txt}\n\n"
        "Escreva a carta de apresentação."
    )

    try:
        carta = llm.ask(system_prompt, user_prompt, max_tokens=600)
        return carta.strip()
    except Exception as erro:
        print(f"Erro ao gerar carta: {erro}")
        return "Erro ao gerar a carta. Tente novamente mais tarde."
