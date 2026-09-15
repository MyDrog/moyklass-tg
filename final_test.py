import os
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv


load_dotenv()


# ============================================================
# CONFIG
# ============================================================

API_KEY = os.getenv("MOYKLASS_API_KEY_TEST")

BASE_URL = "https://api.moyklass.com/v1"

USER_ID = 6323913
SUMMA = 1
PAYMENT_TYPE_ID = 2


# ============================================================
# AUTH
# ============================================================

def get_access_token():
    if not API_KEY:
        raise RuntimeError(
            "Не задан MOYKLASS_API_KEY_TEST в .env"
        )

    response = requests.post(
        f"{BASE_URL}/company/auth/getToken",
        json={
            "apiKey": API_KEY
        },
        headers={
            "Content-Type": "application/json"
        },
        timeout=10
    )

    print("Auth status:", response.status_code)
    print("Auth response:", response.text)

    response.raise_for_status()

    data = response.json()

    access_token = data.get("accessToken")

    if not access_token:
        raise RuntimeError(
            f"В ответе нет accessToken: {data}"
        )

    return access_token


# ============================================================
# CREATE PAYMENT
# ============================================================

def create_payment(access_token):
    now = datetime.now(timezone.utc)

    payload = {
        "userId": USER_ID,
        "date": now.date().isoformat(),
        "summa": SUMMA,
        "userSubscriptionId": None,
        "optype": "income",
        "comment": "Тестовый платеж",
        "createdAt": now.isoformat(),
        "managerId": None,
        "paymentTypeId": PAYMENT_TYPE_ID,
        "cashboxId": None
    }

    print()
    print("Создание платежа:")
    print(payload)

    response = requests.post(
        f"{BASE_URL}/company/payments",
        json=payload,
        headers={
            "Content-Type": "application/json",
            "x-access-token": access_token
        },
        timeout=10
    )

    print()
    print("Payment status:", response.status_code)
    print("Payment response:", response.text)

    response.raise_for_status()

    return response.json()


# ============================================================
# MAIN
# ============================================================

def main():
    print("1. Получаем accessToken...")

    access_token = get_access_token()

    print("AccessToken получен.")

    print()
    print("2. Создаём тестовый платеж...")

    result = create_payment(access_token)

    print()
    print("Платёж успешно создан:")
    print(result)


if __name__ == "__main__":
    main()