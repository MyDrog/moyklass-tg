# tg_sender.py
import os
import json
import asyncio
from telethon import TelegramClient
from telethon.errors import PeerIdInvalidError, RPCError
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

# ---------- main logic ----------

async def get_entity_from_cache(phone: str):
    """Пытаемся взять entity из кэша"""
    phone = normalize_phone(phone)
    cache = load_cache()
    if phone in cache:
        data = cache[phone]
        return InputPeerUser(user_id=data["user_id"], access_hash=data["access_hash"])
    return None

async def get_entity_from_dialogs(phone: str):
    """Ищем entity по существующим диалогам (не трогаем историю)"""
    phone = normalize_phone(phone)
    dialogs = await client.get_dialogs()
    for d in dialogs:
        if hasattr(d.entity, "phone") and normalize_phone(d.entity.phone) == phone:
            entity = d.entity
            # Обновляем кэш
            cache = load_cache()
            cache[phone] = {"user_id": entity.user_id, "access_hash": entity.access_hash}
            save_cache(cache)
            return InputPeerUser(user_id=entity.user_id, access_hash=entity.access_hash)
    return None

async def import_contact(phone: str):
    """Импорт контакта только как последняя мера"""
    phone = normalize_phone(phone)
    contact = InputPhoneContact(client_id=0, phone=phone, first_name="User", last_name="")
    try:
        result = await client(ImportContactsRequest([contact]))
    except RPCError:
        return None

    if not result.users:
        return None

    user = result.users[0]
    cache = load_cache()
    cache[phone] = {"user_id": user.id, "access_hash": user.access_hash}
    save_cache(cache)
    return InputPeerUser(user_id=user.id, access_hash=user.access_hash)

async def send_message_by_phone(phone: str, message: str):
    await client.start(phone=PHONE_NUMBER)

    # 1. Пробуем кэш
    entity = await get_entity_from_cache(phone)

    # 2. Пробуем отправить сообщение
    if entity:
        try:
            await client.send_message(entity, message)
            return
        except PeerIdInvalidError:
            # если не получилось, удаляем из кэша
            cache = load_cache()
            if phone in cache:
                del cache[phone]
                save_cache(cache)
        except RPCError:
            entity = None

    # 3. Пробуем найти диалог
    if not entity:
        entity = await get_entity_from_dialogs(phone)
        if entity:
            try:
                await client.send_message(entity, message)
                return
            except PeerIdInvalidError:
                cache = load_cache()
                if phone in cache:
                    del cache[phone]
                    save_cache(cache)
            except RPCError:
                entity = None

    # 4. Последняя мера — импорт контакта
    if not entity:
        entity = await import_contact(phone)
        if entity:
            try:
                await client.send_message(entity, message)
            except RPCError:
                return

# ---------- test ----------

if __name__ == "__main__":
    asyncio.run(send_message_by_phone("79620051056", "Тестовое сообщение"))
