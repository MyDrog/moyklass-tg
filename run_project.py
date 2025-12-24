import os
import sys
import subprocess
import platform

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
VENV_DIR = os.path.join(PROJECT_DIR, "venv")
REQUIREMENTS_FILE = os.path.join(PROJECT_DIR, "requirements.txt")
ENV_FILE = os.path.join(PROJECT_DIR, ".env")

def run(cmd, shell=False):
    print(f"Running: {' '.join(cmd) if isinstance(cmd, list) else cmd}")
    subprocess.check_call(cmd, shell=shell)

def create_venv():
    if not os.path.exists(VENV_DIR):
        print("Создаем виртуальное окружение...")
        run([sys.executable, "-m", "venv", "venv"])
    else:
        print("Виртуальное окружение уже есть.")

def install_requirements():
    print("Устанавливаем зависимости...")
    if platform.system() == "Windows":
        pip_path = os.path.join(VENV_DIR, "Scripts", "pip.exe")
    else:
        pip_path = os.path.join(VENV_DIR, "bin", "pip")
    run([pip_path, "install", "-r", REQUIREMENTS_FILE])

def activate_and_run_uvicorn():
    # Подгрузка .env перед запуском uvicorn
    python_executable = os.path.join(VENV_DIR, "Scripts" if platform.system() == "Windows" else "bin", "python")
    cmd = [
        python_executable,
        "-c",
        (
            "from dotenv import load_dotenv; "
            f"load_dotenv(r'{ENV_FILE}'); "
            "import uvicorn; "
            "uvicorn.run('app:app', host='0.0.0.0', port=8000)"
        )
    ]
    print("Запуск uvicorn с подгрузкой .env...")
    run(cmd)

def main():
    create_venv()
    install_requirements()

    if not os.path.exists(ENV_FILE):
        print("Файл .env не найден, создайте его с нужными переменными.")
    else:
        print(".env найден, переменные будут подгружены автоматически.")

    activate_and_run_uvicorn()

if __name__ == "__main__":
    main()
