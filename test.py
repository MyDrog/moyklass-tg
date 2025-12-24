from webhook_handler import process_webhook



data = {'companyId': 7133, 'event': 'payment_new', 'init': {'time': 1766532528, 'from': 'CRM', 'managerId': 17845}, 'object': {'userId': 378023, 'paymentId': 31885606, 'summa': 1, 'userSubscriptionId': None, 'paymentTypeId': 1, 'date': '2025-12-24'}, 'changedFields': []}
message = process_webhook(data)
print(message)