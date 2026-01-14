import subprocess

SCREEN_MASK = "moyklass"
UVICORN_PORT = "8000"


def run(cmd, shell=False):
    print("Running:", cmd if shell else " ".join(cmd))
    subprocess.run(cmd, shell=shell, check=False)


def stop_screen():
    print("Проверяем screen-сессии...")
    result = subprocess.run(
        ["screen", "-ls"],
        capture_output=True,
        text=True
    )

    lines = result.stdout.splitlines()
    screens = []

    for line in lines:
        if SCREEN_MASK in line:
            screens.append(line.strip().split()[0])

    if not screens:
        print("Подходящих screen-сессий не найдено")
        return

    for screen_name in screens:
        print(f"Останавливаем screen {screen_name}")
        run(["screen", "-S", screen_name, "-X", "quit"])


def stop_uvicorn():
    print("Проверяем uvicorn на порту 8000...")
    cmd = f"ss -ltnp | grep :{UVICORN_PORT}"
    proc = subprocess.run(cmd, shell=True, capture_output=True, text=True)

    if not proc.stdout:
        print("uvicorn не найден")
        return

    for line in proc.stdout.splitlines():
        if "pid=" in line:
            pid = line.split("pid=")[1].split(",")[0]
            print(f"Останавливаем процесс PID={pid}")
            run(["kill", "-TERM", pid])


def main():
    stop_screen()
    stop_uvicorn()
    print("Проект остановлен.")


if __name__ == "__main__":
    main()
