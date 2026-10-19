import os
import asyncio
import json
import uuid
import time
import logging
from logging.handlers import RotatingFileHandler

from fastapi import FastAPI, Request

from webhook_handler import process_webhook
from tg_sender import client, send_message_by_phone
from max_sender import max_client, send_max_message


# ============================================================
# LOGGING
# ============================================================

log_formatter = logging.Formatter(
    "%(asctime)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger("moyklass")
logger.setLevel(logging.INFO)

file_handler = RotatingFileHandler(
    "webhook.log",
    maxBytes=10 * 1024 * 1024,
    backupCount=5,
    encoding="utf-8",
)

file_handler.setFormatter(log_formatter)
logger.addHandler(file_handler)

console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)
logger.addHandler(console_handler)


# ============================================================
# APP
# ============================================================

app = FastAPI()


# ============================================================
# QUEUES
# ============================================================

webhook_queue = asyncio.Queue()
message_queue = asyncio.Queue()


# ============================================================
# SETTINGS
# ============================================================

SEND_INTERVAL = 3
MAX_MONITOR_INTERVAL = 10
MAX_SEND_TIMEOUT = 20
MAX_START_ATTEMPTS = 3
MAX_START_RETRY_DELAY = 5
MAX_START_TIMEOUT = 120
MAX_ENABLED = os.getenv("ENABLE_MAX", "true").strip().lower() in {
    "1", "true", "yes", "on"
}


# ============================================================
# MAX CONNECTION
# ============================================================

async def start_max_client():
    logger.info("Запуск MAX-клиента...")

    max_task = asyncio.create_task(max_client.start())

    for _ in range(MAX_START_TIMEOUT * 10):
        if max_client._app.started:
            logger.info("MAX подключен")
            return max_task

        if max_task.done():
            try:
                await max_task
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"Ошибка запуска MAX: {e}")
            return None

        await asyncio.sleep(0.1)

    logger.error(f"MAX не подключился за {MAX_START_TIMEOUT} секунд")

    if not max_task.done():
        max_task.cancel()

        try:
            await max_task
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.warning(f"Ошибка завершения неудачного MAX task: {e}")

    return None


async def start_max_with_retries():
    for attempt in range(1, MAX_START_ATTEMPTS + 1):
        logger.info(
            f"Попытка запуска MAX {attempt}/{MAX_START_ATTEMPTS}"
        )
        max_task = await start_max_client()

        if max_task is not None:
            return max_task

        if attempt < MAX_START_ATTEMPTS:
            logger.warning(
                f"MAX не запустился. Повтор через "
                f"{MAX_START_RETRY_DELAY} секунд"
            )
            await asyncio.sleep(MAX_START_RETRY_DELAY)

    raise RuntimeError(
        f"Не удалось запустить MAX за {MAX_START_ATTEMPTS} попытки. "
        "Запуск сервиса отменён."
    )


async def restart_max_client():
    logger.warning("Перезапуск MAX-клиента...")

    try:
        await max_client.stop()
    except Exception as e:
        logger.warning(f"Ошибка при остановке MAX: {e}")

    max_task = getattr(app.state, "max_task", None)

    if max_task is not None and not max_task.done():
        max_task.cancel()

        try:
            await max_task
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.warning(f"Ошибка завершения старого MAX task: {e}")

    app.state.max_task = None

    await asyncio.sleep(2)

    for attempt in range(1, MAX_START_ATTEMPTS + 1):
        logger.info(
            f"Попытка повторного подключения MAX "
            f"{attempt}/{MAX_START_ATTEMPTS}..."
        )

        new_task = await start_max_client()

        if new_task is not None:
            app.state.max_task = new_task
            logger.info("MAX успешно переподключен")
            return True

        if attempt < MAX_START_ATTEMPTS:
            logger.error(
                f"Не удалось подключить MAX. Повтор через "
                f"{MAX_START_RETRY_DELAY} секунд"
            )
            await asyncio.sleep(MAX_START_RETRY_DELAY)

    logger.error(
        f"MAX не подключился после {MAX_START_ATTEMPTS} попыток. "
        "Автоматические попытки остановлены."
    )
    return False


async def max_monitor():
    logger.info("Монитор MAX запущен")

    while True:
        try:
            await asyncio.sleep(MAX_MONITOR_INTERVAL)

            if not max_client._app.started:
                logger.warning("MAX отключен. Запускаем восстановление соединения")

                reconnected = await restart_max_client()
                if not reconnected:
                    logger.error(
                        "Монитор MAX остановлен после исчерпания попыток. "
                        "Приложение продолжит работу с Telegram."
                    )
                    return

        except asyncio.CancelledError:
            logger.info("Монитор MAX остановлен")
            raise

        except Exception as e:
            logger.error(f"Ошибка монитора MAX: {e}")
            await asyncio.sleep(5)


# ============================================================
# MESSAGE WORKER
# ============================================================

async def message_sender_worker():
    logger.info("Worker отправки сообщений запущен")

    while True:
        phone, text, attempts = await message_queue.get()

        try:
            current_attempt = attempts + 1

            logger.info(
                f"Отправка сообщения для {phone}: "
                f"попытка {current_attempt}/3"
            )

            max_result = False
            tg_result = False

            # =========================
            # MAX
            # =========================
            try:
                if max_client._app.started:
                    max_result = await asyncio.wait_for(
                        send_max_message(phone, text),
                        timeout=MAX_SEND_TIMEOUT,
                    )

                    if max_result:
                        logger.info(
                            f"MAX: сообщение отправлено для {phone}, "
                            f"попытка {current_attempt}/3"
                        )
                    else:
                        logger.warning(
                            f"MAX: сообщение не отправлено для {phone}, "
                            f"попытка {current_attempt}/3"
                        )
                else:
                    logger.warning(
                        f"MAX отключен перед отправкой для {phone}; "
                        f"пропускаем MAX и продолжаем отправку в Telegram"
                    )

            except asyncio.TimeoutError:
                logger.warning(
                    f"MAX: превышено время ожидания {MAX_SEND_TIMEOUT}с "
                    f"для {phone}; продолжаем отправку в Telegram"
                )
            except Exception as e:
                logger.error(
                    f"MAX: ошибка отправки для {phone}, "
                    f"попытка {current_attempt}/3: {e}"
                )

            # =========================
            # Telegram
            # =========================
            tg_result_raw = None
            try:
                tg_result_raw = await send_message_by_phone(phone, text)
                tg_result = tg_result_raw is True

                if tg_result:
                    logger.info(
                        f"Telegram: сообщение отправлено для {phone}, "
                        f"попытка {current_attempt}/3"
                    )
                else:
                    logger.warning(
                        f"Telegram: сообщение не отправлено для {phone}, "
                        f"попытка {current_attempt}/3"
                    )

            except Exception as e:
                logger.error(
                    f"Telegram: ошибка отправки для {phone}, "
                    f"попытка {current_attempt}/3: {e}"
                )

            # =========================
            # Результат попытки
            # =========================
            if max_result or tg_result:
                logger.info(
                    f"Отправка завершена для {phone}: "
                    f"Telegram={tg_result_raw}, MAX={max_result}"
                )

            elif current_attempt < 3:
                await message_queue.put(
                    (phone, text, current_attempt)
                )

                logger.info(
                    f"Сообщение для {phone} возвращено в очередь. "
                    f"Следующая попытка: {current_attempt + 1}/3"
                )

            else:
                logger.error(
                    f"Сообщение для {phone} не отправлено ни в один "
                    f"мессенджер после 3 попыток: "
                    f"Telegram={tg_result_raw}, MAX={max_result}"
                )

        except Exception as e:
            logger.exception(
                f"Критическая ошибка обработки сообщения "
                f"для {phone}: {e}"
            )

        finally:
            message_queue.task_done()

        await asyncio.sleep(SEND_INTERVAL)

# ============================================================
# WEBHOOK WORKER
# ============================================================

async def webhook_worker():
    logger.info("Worker обработки webhook запущен")

    while True:
        webhook_id, payload = await webhook_queue.get()

        start_time = time.time()

        try:
            logger.info(
                f"[{webhook_id}] - Начата обработка вебхука"
            )

            result = await asyncio.to_thread(
                process_webhook,
                payload
            )

            elapsed = time.time() - start_time

            logger.info(
                f"[{webhook_id}] - process_webhook завершён за "
                f"{elapsed:.2f}с"
            )

            if result is None:
                logger.warning(
                    f"[{webhook_id}] - process_webhook вернул None"
                )

            else:
                phone = result.get("phone")
                text = result.get("text")

                if phone and text:
                    await message_queue.put(
                        (phone, text, 0)
                    )

                    logger.info(
                        f"[{webhook_id}] - Сообщение добавлено в очередь "
                        f"отправки для {phone}"
                    )

                else:
                    logger.warning(
                        f"[{webhook_id}] - Некорректный результат "
                        f"process_webhook: {result}"
                    )

        except Exception as e:
            logger.exception(
                f"[{webhook_id}] - Ошибка обработки webhook: {e}"
            )

        finally:
            webhook_queue.task_done()


# ============================================================
# STARTUP
# ============================================================

@app.on_event("startup")
async def startup_event():
    logger.info("Запуск приложения")

    # --------------------------------------------------------
    # TELEGRAM
    # --------------------------------------------------------

    try:
        await client.connect()

        if not await client.is_user_authorized():
            logger.warning(
                "Telegram пользователь не авторизован"
            )
        else:
            logger.info(
                "Telegram подключен"
            )

    except Exception as e:
        logger.exception(
            f"Ошибка подключения Telegram: {e}"
        )

    # --------------------------------------------------------
    # MAX
    # --------------------------------------------------------

    app.state.max_task = None
    app.state.max_monitor = None

    if MAX_ENABLED:
        app.state.max_task = await start_max_with_retries()
        app.state.max_monitor = asyncio.create_task(max_monitor())
    else:
        logger.info(
            "Запуск MAX отключен настройкой ENABLE_MAX; "
            "приложение работает без MAX"
        )

    # --------------------------------------------------------
    # WORKERS
    # --------------------------------------------------------

    app.state.webhook_worker = asyncio.create_task(
        webhook_worker()
    )

    app.state.message_worker = asyncio.create_task(
        message_sender_worker()
    )

    logger.info("Приложение запущено")


# ============================================================
# SHUTDOWN
# ============================================================

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Остановка приложения")

    # --------------------------------------------------------
    # MAX MONITOR
    # --------------------------------------------------------

    max_monitor_task = getattr(
        app.state,
        "max_monitor",
        None
    )

    if max_monitor_task is not None:
        max_monitor_task.cancel()

        try:
            await max_monitor_task
        except asyncio.CancelledError:
            pass

    # --------------------------------------------------------
    # WORKERS
    # --------------------------------------------------------

    for name in (
        "webhook_worker",
        "message_worker",
    ):
        task = getattr(app.state, name, None)

        if task is not None:
            task.cancel()

            try:
                await task
            except asyncio.CancelledError:
                pass

    # --------------------------------------------------------
    # TELEGRAM
    # --------------------------------------------------------

    try:
        await client.disconnect()
    except Exception as e:
        logger.warning(
            f"Ошибка отключения Telegram: {e}"
        )

    # --------------------------------------------------------
    # MAX
    # --------------------------------------------------------

    try:
        await max_client.stop()
    except Exception as e:
        logger.warning(
            f"Ошибка остановки MAX: {e}"
        )

    max_task = getattr(
        app.state,
        "max_task",
        None
    )

    if max_task is not None and not max_task.done():
        max_task.cancel()

        try:
            await max_task
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.warning(
                f"Ошибка завершения MAX task: {e}"
            )

    logger.info("Приложение остановлено")


# ============================================================
# WEBHOOK ENDPOINT
# ============================================================

@app.post("/webhook/moyklass")
async def moyklass_webhook(request: Request):
    webhook_id = uuid.uuid4().hex[:8]

    try:
        payload = await request.json()

        logger.info(
            f"[{webhook_id}] - ПОЛУЧЕН ВЕБХУК: "
            f"{payload.get('event')}"
        )

        await webhook_queue.put(
            (webhook_id, payload)
        )

        return {
            "status": "ok"
        }

    except Exception as e:
        logger.exception(
            f"[{webhook_id}] - Ошибка приема webhook: {e}"
        )

        return {
            "status": "error",
            "message": str(e)
        }


# ============================================================
# HEALTHCHECK
# ============================================================

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "telegram_connected": client.is_connected(),
        "max_connected": max_client._app.started,
        "webhook_queue": webhook_queue.qsize(),
        "message_queue": message_queue.qsize(),
    }


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
    )
