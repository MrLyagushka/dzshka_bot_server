import sqlite3
import hashlib
import hmac
import json
import urllib.parse
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Разрешаем запросы с фронтенда (в продакшене укажите свой домен вместо "*")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BOT_TOKEN = "8414515759:AAHLFS38Qj4vedykAbJSDUSu-0zqRYDK6c0"  # ← Замените на токен от @BotFather

def verify_telegram_init_data(init_data: str) -> dict:
    """Валидация подписи Telegram (обязательно для продакшена)"""
    parsed = dict(urllib.parse.parse_qsl(init_data))
    hash_ = parsed.pop('hash')
    # Сортируем ключи и собираем строку для проверки
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
    # Секретный ключ = SHA256(BOT_TOKEN)
    secret_key = hashlib.sha256(BOT_TOKEN.encode()).digest()
    computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    
    if not hmac.compare_digest(computed_hash, hash_):
        raise HTTPException(status_code=403, detail="Неверная подпись Telegram")
    return parsed

def get_db():
    conn = sqlite3.connect("medicines.db")
    conn.row_factory = sqlite3.Row  # Чтобы результаты были словарями
    return conn

def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL
        );
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS medicines (
            medicines_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            name TEXT NOT NULL,
            count TEXT NOT NULL
        ); 
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS days (
            data_medicines_id INTEGER,
            is_taken INTEGER DEFAULT 0
        );
    """)

    conn.commit()
    conn.close()

init_db()

@app.get("/api/medicines")
def get_medicines(request: Request):
    init_data = request.headers.get("X-Telegram-InitData")
    # if not init_data:
    #     raise HTTPException(400, "Отсутствует initData")

    parsed = verify_telegram_init_data(init_data)
    user_info = json.loads(parsed["user"])
    user_id = user_info["id"]

    conn = get_db()
    rows = conn.execute(
        "SELECT id, name FROM users WHERE user_id = ?", 
        (user_id,)
    ).fetchall()
    conn.close()
    
    # Преобразуем строки БД в список словарей для JSON
    return [dict(row) for row in rows]

@app.post("/api/medicines/{medicine_id}/mark")
def mark_medicine(medicine_id: int, request: Request):
    init_data = request.headers.get("X-Telegram-InitData")
    if not init_data:
        raise HTTPException(400, "Отсутствует initData")

    parsed = verify_telegram_init_data(init_data)
    user_info = json.loads(parsed["user"])
    user_id = user_info["id"]

    conn = get_db()
    # Переключаем 0 ↔ 1
    cur = conn.execute(
        "UPDATE medicines SET is_taken = 1 - is_taken WHERE id = ? AND user_id = ?",
        (medicine_id, user_id)
    )
    conn.commit()
    conn.close()

    if cur.rowcount == 0:
        raise HTTPException(404, "Лекарство не найдено или доступно не вам")
    return {"status": "ok"}