from fastapi import FastAPI, Request
from webhook_handler import process_webhook
from tg_sender import client, send_message_by_phone  # импортируем Telethon client и функцию
from os import getenv

app = FastAPI()

@app.on_event("startup")
async def startup_event():
    # Запускаем клиент Telegram при старте приложения
    await client.connect()
    if not await client.is_user_authorized():
        phone = getenv("TG_PHONE_NUMBER")
        await client.start(phone=phone)

@app.post("/webhook/moyklass")
async def moyklass_webhook(request: Request):
    data = await request.json()
    print("Received webhook:", data)
    try:
        message_obj = process_webhook(data)
        if message_obj:
            text = message_obj.get("text")
            phone = message_obj.get("phone")

            print("Webhook message:", text, "Phone:", phone)

            # Отправка в Telegram админу
            admin_phone = getenv("TG_PHONE_NUMBER")
            if text and admin_phone:
                await send_message_by_phone(admin_phone, text)

            # Можно также отправлять на телефон ученика, если нужно:
            # if text and phone:
            #     await send_message_by_phone(phone, text)

    except Exception as e:
        print("Webhook error:", e)

    return {"status": "ok"}
