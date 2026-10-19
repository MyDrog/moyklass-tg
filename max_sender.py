import asyncio
import json
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
CACHE_FILE = BASE_DIR / "max_entity_cache.json"

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


def load_entity_cache() -> dict:
    try:
        with CACHE_FILE.open("r", encoding="utf-8") as file:
            cache = json.load(file)
        return cache if isinstance(cache, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_entity_cache(cache: dict):
    try:
        with CACHE_FILE.open("w", encoding="utf-8") as file:
            json.dump(cache, file, ensure_ascii=False, indent=2)
    except OSError as e:
        print(f"   Не удалось сохранить кеш MAX: {e}")


def remove_entity_from_cache(phone: str):
    cache = load_entity_cache()
    if cache.pop(phone, None) is not None:
        save_entity_cache(cache)


def find_dialog_in_client_cache(phone_key: str):
    """Ищет личный диалог среди чатов и пользователей, уже известных клиенту."""
    for chat in getattr(max_client, "chats", None) or []:
        if not getattr(chat, "is_dialog", False):
            continue

        participants = getattr(chat, "participants", None) or {}
        for participant_id in participants:
            try:
                user = max_client.get_cached_user(int(participant_id))
            except (TypeError, ValueError):
                continue

            user_phone = getattr(user, "phone", None) if user is not None else None
            if user_phone is not None and normalize_phone(str(user_phone)) == phone_key:
                return chat, user

    return None, None


# ============================================================
# SEND MESSAGE
# ============================================================

async def send_max_message(phone: str, message: str) -> bool:

    phone = max_phone(phone)
    phone_key = phone.lstrip("+")

    print(f"2. Ищем пользователя MAX: {phone}")

    # Сначала используем сохранённый chat_id, чтобы не искать номер через API.
    cached_entity = load_entity_cache().get(phone_key)
    cached_chat_id = (
        cached_entity.get("chat_id")
        if isinstance(cached_entity, dict)
        else None
    )

    if cached_chat_id is not None:
        try:
            chat = await max_client.get_chat(cached_chat_id)
            print(
                f"   Чат из кеша найден: "
                f"id={getattr(chat, 'id', cached_chat_id)}"
            )
        except Exception as e:
            print(f"   Сохранённый chat_id MAX недействителен: {e}")
            remove_entity_from_cache(phone_key)
        else:
            try:
                result = await max_client.send_message(
                    chat_id=cached_chat_id,
                    text=message,
                )
                print(
                    "   Сообщение отправлено через кеш: "
                    f"message_id={getattr(result, 'id', None)}"
                )
                return True
            except Exception as e:
                print(f"   Ошибка отправки в чат из кеша: {e}")
                remove_entity_from_cache(phone_key)
                return False

    # Если chat_id ещё не сохранён, ищем номер среди участников локальных
    # личных диалогов до сетевого поиска пользователя.
    chat, user = find_dialog_in_client_cache(phone_key)
    if chat is not None and user is not None:
        print(f"   Диалог найден в кеше чатов: id={chat.id}")

        cache = load_entity_cache()
        cache[phone_key] = {
            "user_id": user.id,
            "chat_id": chat.id,
        }
        save_entity_cache(cache)

        try:
            result = await max_client.send_message(
                chat_id=chat.id,
                text=message,
            )
            print(
                "   Сообщение отправлено через кеш чатов: "
                f"message_id={getattr(result, 'id', None)}"
            )
            return True
        except Exception as e:
            print(f"   Ошибка отправки в чат из кеша чатов: {e}")
            return False

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

    cache = load_entity_cache()
    cache[phone_key] = {
        "user_id": user.id,
        "chat_id": chat_id,
    }
    save_entity_cache(cache)

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

    # Даем время отсканировать QR и завершить подтверждение входа.
    for _ in range(1200):

        if max_client._app.started:
            break

        if client_task.done():
            # Если start() завершился с ошибкой —
            # пробрасываем её.
            await client_task

        await asyncio.sleep(0.1)

    if not max_client._app.started:
        raise RuntimeError(
            "MAX client не удалось запустить за 120 секунд"
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
