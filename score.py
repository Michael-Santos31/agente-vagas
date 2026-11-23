import json
import re
import llm


def formatar_perfil_para_ia(profile_dict):
    """Transforma o dicionário salvo no painel em texto legível para a IA."""
    if not profile_dict:
        return "PERFIL NÃO PREENCHIDO."

    texto = "--- DADOS DO CANDIDATO ---\n"
    texto += f"Nome: {profile_dict.get('nome', 'Não informado')}\n"
    texto += f"Localização: {profile_dict.get('localizacao', 'Não informada')}\n"
    texto += f"Resumo: {profile_dict.get('resumo', '')}\n\n"

    texto += "EXPERIÊNCIAS:\n"
    for exp in profile_dict.get('experiencias', []):
        texto += f"- {exp.get('cargo')} na {exp.get('empresa')} ({exp.get('periodo')}): {exp.get('descricao')}\n"

    texto += "\nFORMAÇÃO E CURSOS:\n"
    for form in profile_dict.get('formacao', []):
        texto += f"- {form}\n"

    texto += "\nHABILIDADES REAIS:\n"
    texto += f"- {', '.join(profile_dict.get('habilidades', []))}\n\n"

    texto += "O QUE BUSCO:\n"
    texto += f"- Cargos desejados: {', '.join(profile_dict.get('cargos_desejados', []))}\n"
    texto += f"- Cargos que NÃO quero: {', '.join(profile_dict.get('cargos_nao_desejados', []))}\n"
    texto += f"- Modelo de trabalho: {profile_dict.get('modelo_trabalho', '')}\n"
    texto += f"- Cidades aceitas: {', '.join(profile_dict.get('cidades_aceitas', []))}\n"
    texto += f"- Salário mínimo: R$ {profile_dict.get('salario_minimo', 'A combinar')}\n\n"

    texto += "MEU JEITO DE ESCREVER (EXEMPLOS):\n"
    for i, exemplo in enumerate(profile_dict.get('exemplos_escrita', [])):
        if exemplo.strip():
            texto += f"--- Exemplo {i + 1} ---\n{exemplo}\n\n"

    return texto


def evaluate(job_text, url, profile_dict):
    """Avalia a vaga usando o DeepSeek e retorna um dicionário com os resultados."""
    perfil_txt = formatar_perfil_para_ia(profile_dict)

    system_prompt = """Você é um avaliador rigoroso de vagas de emprego trabalhando para a pessoa descrita no PERFIL.
Leia o texto da página e responda SOMENTE com um JSON, sem comentários antes ou depois, no formato exato:
{
  "is_job_posting": true/false,
  "title": "título da vaga",
  "company": "nome da empresa",
  "location": "localização",
  "score": 0-100,
  "reason": "2 a 3 frases objetivas justificando a nota",
  "discard_reason": "motivo curto se a nota for baixa, senão vazio",
  "missing_requirements": ["lista de exigências obrigatórias que a pessoa não tem"]
}

REGRAS CRÍTICAS:
1. Se a página NÃO for uma vaga específica (ex: lista de vagas, página inicial, blog, login), defina is_job_posting=false e score=0.
2. A nota mede a compatibilidade REAL. Considere cargo desejado, habilidades que a pessoa TEM, localização, modelo de trabalho, salário mínimo e senioridade.
3. Se a vaga exigir algo obrigatório que a pessoa NÃO tem, reduza muito a nota.
4. Cargo na lista 'NÃO quero', ou salário claramente abaixo do mínimo, resulta em nota abaixo de 40.
5. Vaga fora das cidades aceitas e que não seja remota: nota abaixo de 50.
6. Se o salário não aparecer, não penalize; apenas avise na justificativa.
7. NUNCA presuma habilidade que não esteja no PERFIL."""

    user_prompt = f"AVALIE A SEGUINTE VAGA:\nURL: {url}\n\nTEXTO DA VAGA:\n{job_text}\n\n{perfil_txt}"

    try:
        resposta_ia = llm.ask(system_prompt, user_prompt, max_tokens=800)
    except Exception as e:
        print(f"Erro na IA ao avaliar: {e}")
        return None

    # Tenta extrair o JSON da resposta usando Regex (tolerante a erros da IA)
    try:
        match = re.search(r'\{.*\}', resposta_ia, re.DOTALL)
        if match:
            json_str = match.group(0)
            resultado = json.loads(json_str)
        else:
            resultado = json.loads(resposta_ia)

        # Validações de segurança
        resultado['score'] = max(0, min(100, int(resultado.get('score', 0))))
        resultado['is_job_posting'] = bool(resultado.get('is_job_posting', False))
        resultado['reason'] = resultado.get('reason', 'Sem justificativa.')
        resultado['discard_reason'] = resultado.get('discard_reason', '')
        resultado['missing_requirements'] = resultado.get('missing_requirements', [])

        return resultado

    except Exception as e:
        print(f"Falha ao ler JSON da IA. Resposta bruta: {resposta_ia}")
        # Segunda tentativa: pedir apenas o JSON de forma agressiva
        try:
            user_prompt_correcao = f"A resposta anterior não foi um JSON válido. Responda APENAS o JSON, sem formatação markdown.\n\n{user_prompt}"
            resposta_ia2 = llm.ask(system_prompt, user_prompt_correcao, max_tokens=800)
            match = re.search(r'\{.*\}', resposta_ia2, re.DOTALL)
            return json.loads(match.group(0) if match else resposta_ia2)
        except:
            raise Exception("A IA falhou em retornar um formato válido após 2 tentativas.")


def write_letter(job_text, job, profile_dict):
    """Escreve a carta de apresentação usando o DeepSeek."""
    perfil_txt = formatar_perfil_para_ia(profile_dict)

    system_prompt = """Você escreve textos de apresentação curtos para candidaturas, na VOZ da pessoa do PERFIL.
Imite o tom, o ritmo e o vocabulário dos exemplos da seção 'MEU JEITO DE ESCREVER'.
Português do Brasil, 120 a 180 palavras, sem saudações exageradas, sem clichês ('sou proativo', 'apaixonado por desafios').
REGRAS ABSOLUTAS: 
1. Use SOMENTE fatos que estão no PERFIL. 
2. NÃO invente habilidade, número, empresa ou formação. 
3. Cite 1 ou 2 pontos concretos da vaga que combinem com a experiência real. 
4. Se a vaga pedir algo que a pessoa não tem, não mencione.
Devolva APENAS o texto da carta, nada mais."""

    user_prompt = f"VAGA:\nCargo: {job.get('title')}\nEmpresa: {job.get('company')}\nDescrição: {job_text}\n\n{perfil_txt}\n\nEscreva a carta de apresentação."

    try:
        carta = llm.ask(system_prompt, user_prompt, max_tokens=600)

        # Validação simples anti-alucinação: verifica se a carta cita ferramentas/empresas que não existem no perfil
        # Para isso, pegamos palavras capitalizadas na carta (nomes próprios/ferramentas)
        palavras_carta = set(re.findall(r'\b[A-Z][a-z]+(?:[A-Z][a-z]+)?\b', carta))
        texto_perfil_e_vaga = (perfil_txt + job_text).lower()

        for palavra in palavras_carta:
            # Se for uma palavra longa (nome próprio ou ferramenta) e não estiver no texto original
            if len(palavra) > 4 and palavra.lower() not in texto_perfil_e_vaga and palavra not in ['Português',
                                                                                                   'Brasil', 'Você',
                                                                                                   'Vaga', 'Empresa']:
                carta += "\n\n[REVISAR: possível informação não presente no perfil]"
                break  # Só coloca o aviso uma vez

        return carta.strip()
    except Exception as e:
        print(f"Erro ao gerar carta: {e}")
        return "Erro ao gerar a carta. Tente novamente mais tarde."