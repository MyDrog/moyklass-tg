import requests


BASE_URL = "https://moyklass-proxy.16021998meh.workers.dev"
token1 = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhcGlLZXlJZCI6MTUzMiwic2Vzc2lvbklkIjoiOThiZjg3YmUtNWE3OS00ZWY0LThlYzMtMDJjYjE1ZDBiMmRmIiwiZXhwaXJlc0F0IjoiMjAyNS0xMi0zMFQyMjo1NjoyNCswMDowMCIsInpvbmVJZCI6MSwiY29tcGFueUlkIjo3MTMzLCJpYXQiOjE3NjY1MzA1ODQsImV4cCI6MTc2NzEzNTM4NH0.gcX86PqBPmmVSibRhf4n3TLMIzHZSVNPSfmMMlr8o2o"

def get(path: str):
    try:
        token = token1
        headers = {
            "Content-Type": "application/json",
            "x-access-token": token
        }
        r = requests.get(f"{BASE_URL}{path}", headers=headers, timeout=10)
        if r.status_code == 401:
            # токен устарел, пробуем обновить
            token = _get_new_token()
            headers["x-access-token"] = token
            r = requests.get(f"{BASE_URL}{path}", headers=headers, timeout=10)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.Timeout:
        print(f"[ERROR] Таймаут запроса GET {path}")
        raise
    except requests.exceptions.HTTPError as e:
        print(f"[ERROR] HTTP ошибка при GET {path}: {r.status_code} {r.text}")
        
        raise
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Ошибка запроса GET {path}: {e}")
        raise


def get_user(user_id: int):
    try:
        return get(f"/company/users/{user_id}")
    except Exception as e:
        print(f"[ERROR] Не удалось получить данные пользователя {user_id}: {e}")
        raise
print(get_user(378023))