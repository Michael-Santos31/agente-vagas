import sys
import time
import schedule
from datetime import datetime
import yaml
import pipeline
import db


def rodar_uma_vez():
    print(f"Iniciando execução manual em {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    pipeline.run_once()


def rodar_daemon():
    try:
        with open("config.yaml", "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        horario = config.get("daily_time", "08:00")
    except:
        horario = "08:00"

    print(f"[DAEMON] Agente configurado para rodar todos os dias às {horario}.")
    schedule.every().day.at(horario).do(pipeline.run_once)

    while True:
        schedule.run_pending()
        time.sleep(60)


def rodar_notificacoes():
    try:
        import notify
        notify.check_mail()
    except ImportError:
        print("Módulo de e-mail (notify.py) ainda não foi criado ou está desativado.")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg == "--daemon":
            rodar_daemon()
        elif arg == "--notify":
            rodar_notificacoes()
        else:
            print("Comando inválido. Use: python run.py [--daemon | --notify]")
    else:
        rodar_uma_vez()