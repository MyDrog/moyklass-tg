# main.py
import os
import asyncio
from datetime import datetime
from fastapi import FastAPI, Request
from webhook_handler import process_webhook
from tg_sender import client, send_message_by_phone  # Telethon client и функция

LOG_FILE = "webhook.log"
app = FastAPI()

# Очередь сообщений
message_queue = asyncio.Queue()

# Интервал между отправками
SEND_INTERVAL = 3  # секунды

@app.on_event("startup")
async def startup_event():
    # Запускаем клиент Telegram при старте приложения
    await client.connect()
    if not await client.is_user_authorized():
        phone = os.getenv("TG_PHONE_NUMBER")
        await client.start(phone=phone)
    
    # Запускаем воркер для очереди сообщений
    asyncio.create_task(message_sender_worker())

# Воркер для очереди сообщений
async def message_sender_worker():
    while True:
        phone, text = await message_queue.get()
        try:
            await send_message_by_phone(phone, text)
        except Exception as e:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ошибка {{send_message: {e}}}\n")
        await asyncio.sleep(SEND_INTERVAL)
        message_queue.task_done()

@app.post("/webhook/moyklass")
async def moyklass_webhook(request: Request):
    data = await request.json()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        message_obj = process_webhook(data)

        if message_obj:
            text = message_obj.get("text")
            phone = message_obj.get("phone")

            if text and phone:
                await message_queue.put((phone, text))
            else:
                # Если нет текста или телефона, считаем как ошибку
                with open(LOG_FILE, "a", encoding="utf-8") as f:
                    f.write(f"{timestamp} - ошибка {{text or phone missing}}\n")
                return {"status": "ok"}

        # Если всё отработало
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"{timestamp} - ok\n")

    except Exception as e:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"{timestamp} - ошибка {{{e}}}\n")

    return {"status": "ok"}
