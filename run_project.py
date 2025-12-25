import os
import sys
import subprocess
import platform

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
VENV_DIR = os.path.join(PROJECT_DIR, "venv")
REQUIREMENTS_FILE = os.path.join(PROJECT_DIR, "requirements.txt")
ENV_FILE = os.path.join(PROJECT_DIR, ".env")
SCREEN_NAME = "moyklass-webhook"

def run(cmd, shell=False):
    print(f"Running: {cmd}")
    subprocess.check_call(cmd, shell=shell)

def create_venv():
    if not os.path.exists(VENV_DIR):
        print("Создаем виртуальное окружение...")
        run([sys.executable, "-m", "venv", "venv"])
    else:
        print("Виртуальное окружение уже есть.")

def install_requirements():
    print("Устанавливаем зависимости...")
    pip_path = os.path.join(
        VENV_DIR,
        "Scripts" if platform.system() == "Windows" else "bin",
        "pip"
    )
    run([pip_path, "install", "-r", REQUIREMENTS_FILE])

def run_uvicorn_in_screen():
    if platform.system() == "Windows":
        print("Screen не поддерживается на Windows.")
        return

    python_exec = os.path.join(VENV_DIR, "bin", "python")

    uvicorn_cmd = (
        f"cd {PROJECT_DIR} && "
        f"{python_exec} -c "
        f"\"from dotenv import load_dotenv; "
        f"load_dotenv(r'{ENV_FILE}'); "
        f"import uvicorn; "
        f"uvicorn.run('app:app', host='0.0.0.0', port=8000)\""
    )

    # screen -dmS <name> bash -c "<command>"
    cmd = [
        "screen",
        "-dmS",
        SCREEN_NAME,
        "bash",
        "-c",
        uvicorn_cmd
    ]

    print(f"Запуск uvicorn в screen-сессии '{SCREEN_NAME}'...")
    run(cmd)

def main():
    create_venv()
    install_requirements()

    if not os.path.exists(ENV_FILE):
        print("❌ Файл .env не найден")
        return

    run_uvicorn_in_screen()

    print("\n✅ Сервер запущен в screen")
    print(f"Подключиться: screen -r {SCREEN_NAME}")
    print(f"Список screen: screen -ls")

if __name__ == "__main__":
    main()
