"""Integração com Groq, OpenAI, DeepSeek e Anthropic."""

import os
import time

import yaml
from dotenv import load_dotenv

load_dotenv()


def get_config():
    try:
        with open("config.yaml", "r", encoding="utf-8") as arquivo:
            return yaml.safe_load(arquivo) or {}
    except FileNotFoundError:
        return {}


def _get_settings():
    config = get_config()
    settings = config.get("llm", {}) or {}

    model = os.getenv("LLM_MODEL", settings.get(
        "model", "openai/gpt-oss-20b"
    ))

    provider = os.getenv("LLM_PROVIDER", settings.get("provider", "groq"))

    # O identificador openai/gpt-oss-20b é utilizado no Groq.
    if model.startswith("openai/") and "LLM_PROVIDER" not in os.environ:
        provider = "groq"

    return {
        "provider": provider.lower().strip(),
        "model": model.strip(),
        "base_url": os.getenv("OPENAI_BASE_URL")
    }


def _create_client(provider, base_url=None):
    from openai import OpenAI

    if provider == "groq":
        api_key = os.getenv("GROQ_API_KEY") or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("Configure GROQ_API_KEY nas variáveis de ambiente.")

        return OpenAI(
            api_key=api_key,
            base_url=base_url or "https://api.groq.com/openai/v1"
        )

    if provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("Configure OPENAI_API_KEY.")

        return OpenAI(api_key=api_key, base_url=base_url)

    if provider == "deepseek":
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise ValueError("Configure DEEPSEEK_API_KEY.")

        return OpenAI(
            api_key=api_key,
            base_url=base_url or "https://api.deepseek.com"
        )

    raise ValueError(f"Provedor desconhecido: {provider}")


def ask(system_prompt, user_prompt, max_tokens=1500):
    settings = _get_settings()
    provider = settings["provider"]
    model = settings["model"]

    print(f"[LLM] Provedor: {provider.upper()} | Modelo: {model}")

    ultimo_erro = None

    for tentativa in range(1, 4):
        try:
            if provider in ("groq", "openai", "deepseek"):
                client = _create_client(
                    provider,
                    settings["base_url"]
                )

                resposta = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    max_tokens=max_tokens,
                    timeout=60
                )

                texto = resposta.choices[0].message.content

                if not texto:
                    raise RuntimeError("O modelo retornou uma resposta vazia.")

                return texto.strip()

            if provider == "anthropic":
                import anthropic

                api_key = os.getenv("ANTHROPIC_API_KEY")
                if not api_key:
                    raise ValueError("Configure ANTHROPIC_API_KEY.")

                client = anthropic.Anthropic(
                    api_key=api_key,
                    timeout=60
                )

                resposta = client.messages.create(
                    model=model,
                    max_tokens=max_tokens,
                    system=system_prompt,
                    messages=[
                        {"role": "user", "content": user_prompt}
                    ]
                )

                texto = "".join(
                    bloco.text
                    for bloco in resposta.content
                    if getattr(bloco, "type", None) == "text"
                )

                if not texto:
                    raise RuntimeError("O modelo retornou uma resposta vazia.")

                return texto.strip()

            raise ValueError(f"Provedor não suportado: {provider}")

        except Exception as erro:
            ultimo_erro = erro
            print(f"[LLM] Tentativa {tentativa}/3 falhou: {erro}")

            if tentativa < 3:
                time.sleep(tentativa * 2)

    raise RuntimeError(
        f"Falha na comunicação com {provider}: {ultimo_erro}"
    ) from ultimo_erro


def test_connection():
    try:
        resposta = ask(
            "Você é um assistente objetivo.",
            "Responda apenas: OK",
            max_tokens=20
        )

        return True, f"Conexão estabelecida! Resposta: {resposta}"

    except Exception as erro:
        return False, str(erro)
