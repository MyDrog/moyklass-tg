# tg_sender.py
import os
import json
import asyncio
from telethon import TelegramClient
from telethon.errors import PeerIdInvalidError, RPCError, UserIdInvalidError
from telethon.tl.functions.contacts import ImportContactsRequest
from telethon.tl.types import InputPhoneContact, InputPeerUser
from dotenv import load_dotenv

load_dotenv()

API_ID = int(os.getenv("TG_API_ID"))
API_HASH = os.getenv("TG_API_HASH")
PHONE_NUMBER = os.getenv("TG_PHONE_NUMBER")

CACHE_FILE = "tg_entity_cache.json"

client = TelegramClient("admin_session", API_ID, API_HASH)

# ---------- cache utils ----------

def load_cache() -> dict:
    if not os.path.exists(CACHE_FILE):
        return {}
    with open(CACHE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_cache(cache: dict):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

def normalize_phone(phone: str) -> str:
    return "".join(filter(str.isdigit, phone))

def remove_from_cache(phone: str):
    phone = normalize_phone(phone)
    cache = load_cache()
    if phone in cache:
        del cache[phone]
        save_cache(cache)

# ---------- entity sources ----------

async def get_entity_from_cache(phone: str):
    phone = normalize_phone(phone)
    cache = load_cache()
    data = cache.get(phone)
    if not data:
        return None
    return InputPeerUser(
        user_id=data["user_id"],
        access_hash=data["access_hash"]
    )

async def get_entity_from_dialogs(phone: str):
    phone = normalize_phone(phone)
    async for dialog in client.iter_dialogs():
        entity = dialog.entity
        entity_phone = getattr(entity, "phone", None)
        if entity_phone and normalize_phone(entity_phone) == phone:
            cache = load_cache()
            cache[phone] = {
                "user_id": entity.id,
                "access_hash": entity.access_hash
            }
            save_cache(cache)
            return InputPeerUser(
                user_id=entity.id,
                access_hash=entity.access_hash
            )
    return None

async def import_contact(phone: str):
    phone = normalize_phone(phone)
    contact = InputPhoneContact(
        client_id=0,
        phone=phone,
        first_name="User",
        last_name=""
    )
    try:
        result = await client(ImportContactsRequest([contact]))
    except RPCError:
        return None

    if not result.users:
        return None

    user = result.users[0]
    cache = load_cache()
    cache[phone] = {
        "user_id": user.id,
        "access_hash": user.access_hash
    }
    save_cache(cache)

    return InputPeerUser(
        user_id=user.id,
        access_hash=user.access_hash
    )

# ---------- sending ----------

async def safe_send(entity, phone: str, message: str) -> bool | None:
    """
    True  — сообщение отправлено.
    False — временная/иная RPC-ошибка; кеш оставляем.
    None  — Telegram отклонил получателя; кеш удалён, можно обновить entity.
    """
    if entity is None:
        return False

    try:
        await client.send_message(entity, message)
        return True

    except (PeerIdInvalidError, UserIdInvalidError):
        remove_from_cache(phone)
        return None

    except RPCError:
        return False

async def send_message_by_phone(phone: str, message: str) -> bool:
    await client.start(phone=PHONE_NUMBER)

    # 1. cache
    entity = await get_entity_from_cache(phone)
    if entity is not None:
        result = await safe_send(entity, phone, message)
        if result is not None:
            return result

    # 2. dialogs
    entity = await get_entity_from_dialogs(phone)
    if entity is not None:
        result = await safe_send(entity, phone, message)
        if result is not None:
            return result

    # 3. import (последний шанс)
    entity = await import_contact(phone)
    return await safe_send(entity, phone, message) is True

# ---------- test ----------

if __name__ == "__main__":
    asyncio.run(
        send_message_by_phone("79620051056", "Тестовое сообщение")
    )
