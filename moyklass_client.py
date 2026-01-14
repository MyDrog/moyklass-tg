import os
import requests
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://moyklass-proxy.16021998meh.workers.dev"
API_KEY = os.getenv("MOYKLASS_API_KEY")

_token_cache = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhcGlLZXlJZCI6MTUzMiwic2Vzc2lvbklkIjoiOThiZjg3YmUtNWE3OS00ZWY0LThlYzMtMDJjYjE1ZDBiMmRmIiwiZXhwaXJlc0F0IjoiMjAyNS0xMi0zMFQyMjo1NjoyNCswMDowMCIsInpvbmVJZCI6MSwiY29tcGFueUlkIjo3MTMzLCJpYXQiOjE3NjY1MzA1ODQsImV4cCI6MTc2NzEzNTM4NH0.gcX86PqBPmmVSibRhf4n3TLMIzHZSVNPSfmMMlr8o2o"
_token_expiry = datetime(2025, 12, 26, 0, 0, 0, tzinfo=timezone.utc)


def _get_new_token():
    global _token_cache, _token_expiry
    try:
        resp = requests.post(
            f"{BASE_URL}/company/auth/getToken",
            json={"apiKey": API_KEY},
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        resp.raise_for_status()
        data = resp.json()
        _token_cache = data["accessToken"]
        _token_expiry = datetime.fromisoformat(data["expiresAt"])
        return _token_cache
    except requests.exceptions.RequestException as e:
        raise


def _get_token():
    global _token_cache, _token_expiry
    now = datetime.now(timezone.utc)
    if not _token_cache or now >= _token_expiry - timedelta(minutes=5):
        return _get_new_token()
    return _token_cache


def get(path: str):
    try:
        token = _get_token()
        headers = {
            "Content-Type": "application/json",
            "x-access-token": token
        }
        r = requests.get(f"{BASE_URL}{path}", headers=headers, timeout=10)
        if r.status_code == 401:
            token = _get_new_token()
            headers["x-access-token"] = token
            r = requests.get(f"{BASE_URL}{path}", headers=headers, timeout=10)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.RequestException:
        raise


def get_user(user_id: int):
    try:
        return get(f"/company/users/{user_id}")
    except Exception:
        raise


def get_payment(payment_id: int):
    try:
        return get(f"/company/payments/{payment_id}")
    except Exception:
        raise


def get_lesson(lesson_id: int):
    try:
        return get(f"/company/lessons/{lesson_id}")
    except Exception:
        raise


def get_class(class_id: int):
    """Получить информацию о группе по classId"""
    try:
        return get(f"/company/classes/{class_id}")
    except Exception:
        raise


def get_course(course_id: int):
    """Получить информацию о курсе по courseId"""
    try:
        data = get(f"/company/courses/?courseId={course_id}")
        if isinstance(data, list) and data:
            return data[0]
        return {}
    except Exception:
        raise
