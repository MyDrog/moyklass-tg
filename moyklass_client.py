import os
import requests
import time
import threading
from collections import deque
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv("MOYKLASS_BASE_URL")
API_KEY = os.getenv("MOYKLASS_API_KEY")

_REQUEST_LIMIT = 2
_REQUEST_WINDOW_SECONDS = 1.0
_REQUEST_WINDOW_MARGIN_SECONDS = 0.001
_request_timestamps = deque()
_request_limit_lock = threading.Lock()


def _wait_for_request_slot():
    """Ограничивает все запросы к Moyklass двумя за скользящую секунду."""
    with _request_limit_lock:
        while True:
            now = time.monotonic()

            while (
                _request_timestamps
                and now - _request_timestamps[0] > _REQUEST_WINDOW_SECONDS
            ):
                _request_timestamps.popleft()

            if len(_request_timestamps) < _REQUEST_LIMIT:
                _request_timestamps.append(now)
                return

            wait_seconds = (
                _request_timestamps[0]
                + _REQUEST_WINDOW_SECONDS
                + _REQUEST_WINDOW_MARGIN_SECONDS
                - now
            )
            time.sleep(max(wait_seconds, _REQUEST_WINDOW_MARGIN_SECONDS))

_token_cache = None
_token_expiry = datetime(2025, 12, 26, 0, 0, 0, tzinfo=timezone.utc)
_token_expiry = datetime(2025, 12, 26, 0, 0, 0, tzinfo=timezone.utc)


def _get_new_token():
    global _token_cache, _token_expiry
    try:
        _wait_for_request_slot()
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
        _wait_for_request_slot()
        r = requests.get(f"{BASE_URL}{path}", headers=headers, timeout=10)
        if r.status_code == 401:
            token = _get_new_token()
            headers["x-access-token"] = token
            _wait_for_request_slot()
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
