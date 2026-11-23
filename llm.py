import os
import time
import yaml
from dotenv import load_dotenv

# Carrega as variáveis do arquivo .env
load_dotenv()


def get_config():
    """Lê o arquivo config.yaml para saber qual IA usar."""
    try:
        with open("config.yaml", "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        return {"llm": {"provider": "deepseek", "model": "deepseek-chat"}}


def ask(system_prompt, user_prompt, max_tokens=1500):
    """
    Conecta com a API do DeepSeek e retorna o texto.
    Possui sistema de tentativas (retry) caso a rede falhe.
    """
    config = get_config().get("llm", {})
    provider = os.getenv("LLM_PROVIDER", config.get("provider", "deepseek")).lower()
    model = config.get("model", "deepseek-chat")

    print(f"[LLM] Conectando ao provedor: {provider.upper()} (Modelo: {model})")

    tentativas = 3
    for tentativa in range(1, tentativas + 1):
        try:
            if provider == "deepseek":
                # 🔥 INTEGRAÇÃO COM O DEEPSEEK 🔥
                api_key = os.getenv("DEEPSEEK_API_KEY")
                if not api_key:
                    raise ValueError("Chave DEEPSEEK_API_KEY não encontrada no arquivo .env")

                from openai import OpenAI
                client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

                response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    max_tokens=max_tokens,
                    timeout=60
                )
                return response.choices[0].message.content

            elif provider == "anthropic":
                api_key = os.getenv("ANTHROPIC_API_KEY")
                if not api_key: raise ValueError("Chave ANTHROPIC_API_KEY ausente.")
                import anthropic
                client = anthropic.Anthropic(api_key=api_key)
                response = client.messages.create(
                    model=model, max_tokens=max_tokens, system=system_prompt,
                    messages=[{"role": "user", "content": user_prompt}]
                )
                return response.content[0].text

            elif provider == "openai":
                api_key = os.getenv("OPENAI_API_KEY")
                if not api_key: raise ValueError("Chave OPENAI_API_KEY ausente.")
                from openai import OpenAI
                client = OpenAI(api_key=api_key)
                response = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
                    max_tokens=max_tokens
                )
                return response.choices[0].message.content

            else:
                raise ValueError(f"Provedor '{provider}' desconhecido.")

        except Exception as e:
            erro_msg = str(e)
            print(f"[LLM] Erro na tentativa {tentativa}/{tentativas}: {erro_msg}")
            if tentativa == tentativas:
                raise Exception(f"Falha ao contatar a IA após {tentativas} tentativas. Erro: {erro_msg}")
            time.sleep(tentativa * 2)  # Espera 2s, depois 4s


# Função utilitária para o painel web (testar a conexão)
def test_connection():
    """Testa se a chave do DeepSeek está funcionando (usado no dashboard)."""
    try:
        res = ask("Você é um assistente.", "Responda apenas: OK", max_tokens=10)
        return True, "Conexão com a IA estabelecida com sucesso!"
    except Exception as e:
        return False, str(e)