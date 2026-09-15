import asyncio
from pathlib import Path

import qrcode
from dotenv import load_dotenv
from pymax import WebClient


load_dotenv()


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

WORK_DIR = BASE_DIR / "max_cache"
SESSION_NAME = "max_web_session.db"
QR_FILE = BASE_DIR / "max_qr.png"

WORK_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# QR PROVIDER
# ============================================================

class SaveQr:
    async def show_qr(self, qr_url: str):
        img = qrcode.make(qr_url)
        img.save(QR_FILE)

        print(f"MAX QR-код сохранён: {QR_FILE}")
        print("Отсканируй его приложением MAX.")


# ============================================================
# MAX CLIENT
# ============================================================

max_client = WebClient(
    work_dir=str(WORK_DIR),
    session_name=SESSION_NAME,
    qr_provider=SaveQr(),
)


# ============================================================
# PHONE
# ============================================================

def normalize_phone(phone: str) -> str:
    return "".join(filter(str.isdigit, phone))


def max_phone(phone: str) -> str:
    phone = normalize_phone(phone)

    if phone.startswith("8"):
        phone = "7" + phone[1:]

    if not phone.startswith("7"):
        raise ValueError(f"Некорректный номер MAX: {phone}")

    return "+" + phone


# ============================================================
# SEND MESSAGE
# ============================================================

async def send_max_message(phone: str, message: str) -> bool:

    phone = max_phone(phone)

    print(f"2. Ищем пользователя MAX: {phone}")

    try:
        user = await max_client.search_by_phone(phone)

        print(
            f"   Пользователь найден: "
            f"id={user.id}"
        )

    except Exception as e:
        print(f"   Ошибка поиска пользователя: {e}")
        return False

    # --------------------------------------------------------
    # ID текущего пользователя
    # --------------------------------------------------------

    try:
        my_user_id = max_client.me.contact.id
    except Exception:
        my_user_id = max_client.me.id

    print(f"3. ID текущего аккаунта: {my_user_id}")
    print(f"   ID получателя: {user.id}")

    # --------------------------------------------------------
    # CHAT ID
    # --------------------------------------------------------

    try:
        chat_id = user.get_chat_id(my_user_id)

        print(f"4. chat_id: {chat_id}")

    except Exception as e:
        print(f"   Ошибка получения chat_id: {e}")
        return False

    # --------------------------------------------------------
    # GET CHAT
    # --------------------------------------------------------

    try:
        chat = await max_client.get_chat(chat_id)

        print(
            f"5. Чат найден: "
            f"id={getattr(chat, 'id', None)}"
        )

    except Exception as e:
        print(f"   Ошибка получения чата: {e}")
        return False

    # --------------------------------------------------------
    # SEND
    # --------------------------------------------------------

    try:
        print("6. Отправляем сообщение...")

        result = await max_client.send_message(
            chat_id=chat_id,
            text=message,
        )

        print(
            "7. Сообщение отправлено: "
            f"message_id={getattr(result, 'id', None)}"
        )

        return True

    except Exception as e:
        print(f"   Ошибка отправки: {e}")
        return False


# ============================================================
# MAIN
# ============================================================

async def main():

    print("1. Запускаем MAX...")

    # start() блокируется до закрытия WebSocket,
    # поэтому запускаем его отдельной задачей.
    client_task = asyncio.create_task(
        max_client.start()
    )

    # --------------------------------------------------------
    # Ждём фактического запуска клиента
    # --------------------------------------------------------

    for _ in range(100):

        if max_client._app.started:
            break

        if client_task.done():
            # Если start() завершился с ошибкой —
            # пробрасываем её.
            await client_task

        await asyncio.sleep(0.1)

    if not max_client._app.started:
        raise RuntimeError(
            "MAX client не удалось запустить за 10 секунд"
        )

    print("MAX client успешно запущен.")

    # --------------------------------------------------------
    # Информация об аккаунте
    # --------------------------------------------------------

    try:
        print(
            f"MAX profile id: "
            f"{max_client.me.id}"
        )
    except Exception:
        pass

    try:
        print(
            f"MAX contact id: "
            f"{max_client.me.contact.id}"
        )
    except Exception:
        pass

    print()

    # --------------------------------------------------------
    # ТЕСТОВАЯ ОТПРАВКА
    # --------------------------------------------------------

    result = await send_max_message(
        phone="79620051056",
        message="Тестовое сообщение из MAX",
    )

    print()
    print(f"Результат отправки: {result}")

    # --------------------------------------------------------
    # Оставляем MAX подключённым
    # --------------------------------------------------------

    if result:
        print("MAX остаётся подключённым.")
        print("Для завершения нажми Ctrl+C.")

        try:
            await client_task
        except asyncio.CancelledError:
            pass

    else:
        # Если отправка не удалась — закрываем клиент.
        await max_client.stop()

        try:
            await client_task
        except asyncio.CancelledError:
            pass


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nMAX остановлен.")