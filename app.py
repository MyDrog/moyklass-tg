from fastapi import FastAPI, Request
from webhook_handler import process_webhook

app = FastAPI()


@app.post("/webhook/moyklass")
async def moyklass_webhook(request: Request):
    data = await request.json()
    print("Received webhook:", data)
    try:
        message = process_webhook(data)
        if message:
            print(message)  # потом сюда будет отправка в TG
    except Exception as e:
        print("Webhook error:", e)

    return {"status": "ok"}
