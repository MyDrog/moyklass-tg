# tg_sender.py
import os
import asyncio
from telethon import TelegramClient
from telethon.errors.rpcerrorlist import UserNotMutualContactError
from telethon.tl.functions.contacts import ImportContactsRequest
from telethon.tl.types import InputPhoneContact
from dotenv import load_dotenv

# Загружаем переменные окружения из .env
load_dotenv()

API_ID = int(os.getenv("TG_API_ID"))
API_HASH = os.getenv("TG_API_HASH")
PHONE_NUMBER = os.getenv("TG_PHONE_NUMBER")  # админский номер '7XXXXXXXXXX'

# Создаём клиент, сессия хранится в файле 'admin_session.session'
client = TelegramClient('admin_session', API_ID, API_HASH)

async def send_message_by_phone(phone: str, message: str):
    # Запускаем клиент, сессия один раз сохранится
    await client.start(phone=PHONE_NUMBER)

    # Нормализуем номер (убираем лишние символы)
    phone = ''.join(filter(str.isdigit, phone))

    entity = None
    try:
        # Пробуем получить существующего пользователя
        entity = await client.get_entity(phone)
    except ValueError:
        # Если нет, добавляем временно в контакты
        contact = InputPhoneContact(client_id=0, phone=phone, first_name="User", last_name="")
        result = await client(ImportContactsRequest([contact]))
        if result.users:
            entity = result.users[0]

    if entity:
        await client.send_message(entity, message)
        print(f"Message sent to {phone}")
    else:
        print(f"Cannot send message to {phone}, user not found")

# Тестовый запуск
if __name__ == "__main__":
    phone_test = "79620051056"  # номер ученика из CRM
    message_test = "Паша лох"
    asyncio.run(send_message_by_phone(phone_test, message_test))
