from fastapi import FastAPI, Request
from webhook_handler import process_webhook
from tg_sender import client, send_message_by_phone  # импортируем Telethon client и функцию

app = FastAPI()

@app.on_event("startup")
async def startup_event():
    # Запускаем клиент Telegram при старте приложения
    await client.connect()
    if not await client.is_user_authorized():
        from os import getenv
        phone = getenv("TG_PHONE_NUMBER")
        await client.start(phone=phone)

@app.post("/webhook/moyklass")
async def moyklass_webhook(request: Request):
    data = await request.json()
    print("Received webhook:", data)
    try:
        message = process_webhook(data)
        if message:
            print("Webhook message:", message)
            # Отправка в Telegram админу
            admin_phone = getenv("TG_PHONE_NUMBER")
            await send_message_by_phone(admin_phone, message)
    except Exception as e:
        print("Webhook error:", e)

    return {"status": "ok"}
