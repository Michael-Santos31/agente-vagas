import os
import requests
from imap_tools import MailBox, AND
from datetime import datetime, timedelta
import db


def classificar_email(assunto, texto_inicio):
    """Olha o assunto e o começo do texto para ver se é algo importante."""
    texto = (assunto + " " + texto_inicio).lower()

    if any(p in texto for p in ['teste', 'avaliação', 'avaliacao', 'desafio', 'case']):
        return "teste"
    if any(p in texto for p in ['entrevista', 'convite', 'agendamento', 'bate-papo']):
        return "entrevista"
    if any(p in texto for p in ['prazo', 'até o dia', 'ate o dia', 'último dia', 'ultimo dia', 'expira']):
        return "prazo"
    if any(p in texto for p in ['candidatura', 'processo seletivo', 'currículo', 'curriculo', 'vaga']):
        return "outro"

    return None  # Não é relacionado a vagas


def enviar_notificacao(titulo, mensagem):
    """Envia um push para o celular via ntfy.sh."""
    topico = os.getenv("NTFY_TOPIC")
    if not topico:
        print("[AVISO] NTFY_TOPIC não configurado. Notificação não enviada.")
        return

    try:
        # O ntfy requer que o texto seja enviado no corpo da requisição
        requests.post(
            f"https://ntfy.sh/{topico}",
            data=mensagem.encode("utf-8"),
            headers={
                "Title": titulo,
                "Priority": "high",
                "Tags": "email,robot"
            }
        )
        print(f"[NTFY] Notificação enviada: {titulo}")
    except Exception as e:
        print(f"[ERRO] Falha ao enviar notificação ntfy: {e}")


def checar_conta(host, user, senha, nome_conta):
    """Conecta na conta IMAP e processa e-mails dos últimos 3 dias."""
    if not host or not user or not senha:
        return

    print(f"[E-MAIL] Checando conta: {nome_conta} ({user})")

    try:
        # Se a porta não for especificada, o imap_tools usa 993 por padrão (SSL)
        with MailBox(host).login(user, senha) as mailbox:
            # Pega e-mails dos últimos 3 dias
            data_limite = datetime.now() - timedelta(days=3)

            # mark_seen=False garante que não vamos marcar como lido no seu e-mail real
            for msg in mailbox.fetch(AND(date_gte=data_limite.date()), mark_seen=False):
                kind = classificar_email(msg.subject, msg.text[:500])

                if not kind:
                    continue  # Ignora e-mails de spam ou não relacionados

                # Verifica se já avisamos sobre esse e-mail específico
                with db.conn() as c:
                    cursor = c.execute("SELECT id FROM email_events WHERE message_uid = ?", (msg.uid,))
                    if cursor.fetchone():
                        continue  # Já processado, pula para o próximo

                    # Salva no banco
                    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    c.execute('''
                        INSERT INTO email_events (message_uid, account, subject, kind, received_at, notified)
                        VALUES (?, ?, ?, ?, ?, 1)
                    ''', (msg.uid, nome_conta, msg.subject, kind, agora))

                # Envia para o celular
                titulo = f"Novo e-mail: {kind.upper()}"
                mensagem = f"De: {msg.from_}\nAssunto: {msg.subject}\n\nAbra seu e-mail para ler."
                enviar_notificacao(titulo, mensagem)

    except Exception as e:
        print(f"[ERRO] Falha ao checar e-mail {user}: {e}")


def check_mail():
    """Função principal chamada pelo run.py"""
    print("=== INICIANDO CHECAGEM DE E-MAILS ===")

    # Conta 1
    checar_conta(
        os.getenv("EMAIL_1_HOST"),
        os.getenv("EMAIL_1_USER"),
        os.getenv("EMAIL_1_APP_PASSWORD"),
        "Conta 1"
    )

    # Conta 2 (se configurada)
    checar_conta(
        os.getenv("EMAIL_2_HOST"),
        os.getenv("EMAIL_2_USER"),
        os.getenv("EMAIL_2_APP_PASSWORD"),
        "Conta 2"
    )
    print("=== CHECAGEM FINALIZADA ===")