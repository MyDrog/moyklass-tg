from webhook_handler import process_webhook
from tg_sender import send_message_by_phone
import asyncio

# Пример тестового вебхука
data = {
    'companyId': 7133,
    'event': 'payment_new',
    'init': {'time': 1766532528, 'from': 'CRM', 'managerId': 17845},
    'object': {'userId': 378023, 'paymentId': 31885606, 'summa': 1, 'userSubscriptionId': None, 'paymentTypeId': 1, 'date': '2025-12-24'},
    'changedFields': []
}

message_obj = process_webhook(data)
print("Webhook processed:", message_obj)

if message_obj:
    text = message_obj.get("text")
    phone = message_obj.get("phone")

    if text and phone:
        # Функция асинхронная, оборачиваем в asyncio.run
        asyncio.run(send_message_by_phone(phone, text))
