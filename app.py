import os
import asyncio
import json
import uuid
import time
import logging
from datetime import datetime
from logging.handlers import RotatingFileHandler
from fastapi import FastAPI, Request
from webhook_handler import process_webhook
from tg_sender import client, send_message_by_phone  # Telethon client и функция

# Настройка логирования
log_formatter = logging.Formatter(
    '%(asctime)s - %(levelname)s - [%(request_id)s] - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Файловый обработчик с ротацией (10 MB, 5 бэкапов)
file_handler = RotatingFileHandler(
    'webhook.log', 
    maxBytes=10*1024*1024,  # 10 MB
    backupCount=5,
    encoding='utf-8'
)
file_handler.setFormatter(log_formatter)

# Консольный обработчик для отладки
console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(file_handler)
logger.addHandler(console_handler)

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
        request_id = str(uuid.uuid4())[:8]
        log_context = {"request_id": f"send_{request_id}"}
        
        try:
            start_time = time.time()
            await send_message_by_phone(phone, text)
            duration = time.time() - start_time
            
            logger.info(
                f"отправлено сообщение для {phone}: {text[:50]}... | время: {duration:.2f}с",
                extra=log_context
            )
        except Exception as e:
            logger.error(
                f"ошибка при отправке для {phone}: {e}", 
                extra=log_context,
                exc_info=True
            )
        await asyncio.sleep(SEND_INTERVAL)
        message_queue.task_done()

@app.post("/webhook/moyklass")
async def moyklass_webhook(request: Request):
    start_time = time.time()
    request_id = str(uuid.uuid4())[:8]  # Короткий ID: "a1b2c3d4"
    log_context = {"request_id": request_id}
    
    # Получаем данные вебхука
    data = await request.json()
    
    # Логируем получение вебхука
    logger.info(
        f"ПОЛУЧЕН ВЕБХУК: {data.get('event')} | companyId: {data.get('companyId')}",
        extra=log_context
    )
    
    # Логируем полные данные вебхука (на уровне DEBUG, чтобы не засорять лог)
    logger.debug(
        f"Данные вебхука: {json.dumps(data, ensure_ascii=False)}",
        extra=log_context
    )

    try:
        process_start = time.time()
        message_obj = process_webhook(data)
        process_duration = time.time() - process_start
        
        logger.debug(
            f"process_webhook выполнен за {process_duration:.2f}с",
            extra=log_context
        )

        if message_obj:
            text = message_obj.get("text")
            phone = message_obj.get("phone")

            if text and phone:
                await message_queue.put((phone, text))
                logger.info(
                    f"сообщение добавлено в очередь для {phone} | обработка: {process_duration:.2f}с",
                    extra=log_context
                )
            else:
                logger.warning(
                    f"ОШИБКА: отсутствует text или phone в обработанных данных | message_obj: {message_obj}",
                    extra=log_context
                )
                return {"status": "ok"}

        # Если всё отработало
        total_duration = time.time() - start_time
        logger.info(
            f"вебхук успешно обработан | всего: {total_duration:.2f}с",
            extra=log_context
        )

    except Exception as e:
        error_duration = time.time() - start_time
        logger.error(
            f"ОШИБКА при обработке вебхука через {error_duration:.2f}с: {str(e)}",
            extra=log_context,
            exc_info=True  # Добавляет stack trace
        )

    return {"status": "ok"}