import os

from run_project import (
    ENV_FILE,
    create_venv,
    install_requirements,
    run_uvicorn_in_screen,
)


SCREEN_NAME = "moyklass-webhook-no-max"


def main():
    create_venv()
    install_requirements()

    if not os.path.exists(ENV_FILE):
        print("❌ Файл .env не найден")
        return

    run_uvicorn_in_screen(enable_max=False, screen_name=SCREEN_NAME)

    print("\n✅ Сервер запущен без MAX в screen")
    print(f"Подключиться: screen -r {SCREEN_NAME}")
    print("Список screen: screen -ls")


if __name__ == "__main__":
    main()
