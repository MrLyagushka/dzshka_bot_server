import sqlite3
import json
from fastapi import FastAPI, Request, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    conn = sqlite3.connect("medicines.db")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    # ⚠️ Структура БД — БЕЗ ИЗМЕНЕНИЙ, как в оригинале
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

async def get_user_id_from_request(request: Request) -> int:
    """Извлекаем user_id из JSON-тела запроса"""
    try:
        body = await request.json()
        user_id = body.get("user_id")
        if not isinstance(user_id, int) or user_id <= 0:
            raise ValueError("user_id must be positive integer")
        return user_id
    except Exception:
        raise HTTPException(status_code=400, detail="Отсутствует или некорректный user_id в теле запроса")

@app.get("/api/medicines")
async def get_medicines(request: Request):
    user_id = await get_user_id_from_request(request)

    conn = get_db()
    # JOIN с days, чтобы получить is_taken. 
    # Используем LEFT JOIN — если записи в days нет, считаем is_taken=0
    rows = conn.execute("""
        SELECT 
            m.medicines_id AS id,
            m.name,
            m.count AS scheduled_time,
            COALESCE(d.is_taken, 0) AS is_taken
        FROM medicines m
        LEFT JOIN days d ON m.medicines_id = d.data_medicines_id
        WHERE m.user_id = ?
    """, (user_id,)).fetchall()
    conn.close()
    
    return [dict(row) for row in rows]

@app.post("/api/medicines/{medicine_id}/mark")
async def mark_medicine(medicine_id: int, request: Request):
    user_id = await get_user_id_from_request(request)

    conn = get_db()
    
    # Проверяем, что лекарство принадлежит пользователю
    med = conn.execute(
        "SELECT medicines_id FROM medicines WHERE medicines_id = ? AND user_id = ?",
        (medicine_id, user_id)
    ).fetchone()
    
    if not med:
        conn.close()
        raise HTTPException(status_code=404, detail="Лекарство не найдено или доступно не вам")
    
    # Обновляем is_taken в таблице days (UPSERT: INSERT OR REPLACE)
    # Сначала читаем текущее значение
    cur = conn.execute(
        "SELECT is_taken FROM days WHERE data_medicines_id = ?",
        (medicine_id,)
    ).fetchone()
    
    new_value = 0 if cur and cur[0] == 1 else 1
    
    # Используем INSERT OR REPLACE для простоты (SQLite)
    conn.execute(
        "INSERT OR REPLACE INTO days (data_medicines_id, is_taken) VALUES (?, ?)",
        (medicine_id, new_value)
    )
    conn.commit()
    conn.close()

    return {"status": "ok"}