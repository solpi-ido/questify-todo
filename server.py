import sqlite3
from fastapi import FastAPI, HTTPException, Header
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import os

app = FastAPI(title="Questify Todo API")

DB_PATH = "/home/ido/projects/questify-todo/questify.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS quests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            type TEXT NOT NULL,
            energy TEXT NOT NULL,
            xp INTEGER NOT NULL,
            completed BOOLEAN NOT NULL,
            category TEXT NOT NULL
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS player (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            level INTEGER NOT NULL,
            xp INTEGER NOT NULL,
            next_level_xp INTEGER NOT NULL,
            streak INTEGER NOT NULL,
            coins INTEGER NOT NULL
        )
    """)
    
    conn.commit()
    conn.close()

init_db()

class UserAuth(BaseModel):
    username: str
    password: str

class QuestCreate(BaseModel):
    title: str
    type: str
    energy: str
    xp: int
    category: str

@app.post("/api/register")
def register(user: UserAuth):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (user.username, user.password))
        user_id = cursor.lastrowid
        cursor.execute("INSERT INTO player (user_id, level, xp, next_level_xp, streak, coins) VALUES (?, 1, 0, 500, 1, 0)", (user_id,))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        raise HTTPException(status_code=400, detail="שם המשתמש כבר קיים במערכת")
    conn.close()
    return {"status": "registered", "user_id": user_id, "username": user.username}

@app.post("/api/login")
def login(user: UserAuth):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username = ? AND password = ?", (user.username, user.password))
    db_user = cursor.fetchone()
    conn.close()
    if not db_user:
        raise HTTPException(status_code=400, detail="שם משתמש או סיסמה שגויים")
    return {"status": "logged_in", "user_id": db_user["id"], "username": db_user["username"]}

@app.get("/api/quests")
def get_quests(user_id: int):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM quests WHERE user_id = ? ORDER BY id DESC", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

@app.post("/api/quests")
def add_quest(quest: QuestCreate, user_id: int):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO quests (user_id, title, type, energy, xp, completed, category) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (user_id, quest.title, quest.type, quest.energy, quest.xp, False, quest.category)
    )
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()
    return {"id": new_id, "status": "created"}

@app.delete("/api/quests/{quest_id}")
def delete_quest(quest_id: int):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM quests WHERE id = ?", (quest_id,))
    conn.commit()
    conn.close()
    return {"status": "deleted"}

@app.patch("/api/quests/{quest_id}/toggle")
def toggle_quest(quest_id: int):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM quests WHERE id = ?", (quest_id,))
    quest = cursor.fetchone()
    if not quest:
        conn.close()
        raise HTTPException(status_code=404, detail="Quest not found")
    
    user_id = quest["user_id"]
    new_completed = 0 if quest["completed"] else 1
    cursor.execute("UPDATE quests SET completed = ? WHERE id = ?", (new_completed, quest_id))
    
    # Update player XP for this user
    cursor.execute("SELECT * FROM player WHERE user_id = ?", (user_id,))
    player = cursor.fetchone()
    p_level = player["level"]
    p_xp = player["xp"]
    p_next = player["next_level_xp"]
    p_coins = player["coins"]
    q_xp = quest["xp"]

    if new_completed == 1:
        p_xp += q_xp
        p_coins += q_xp // 2
        if p_xp >= p_next:
            p_level += 1
            p_xp -= p_next
            p_next = int(p_next * 1.3)
    else:
        p_xp = max(0, p_xp - q_xp)

    cursor.execute("UPDATE player SET level = ?, xp = ?, next_level_xp = ?, coins = ? WHERE user_id = ?", (p_level, p_xp, p_next, p_coins, user_id))
    conn.commit()
    conn.close()
    return {"status": "updated", "completed": bool(new_completed)}

@app.get("/api/player")
def get_player(user_id: int):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM player WHERE user_id = ?", (user_id,))
    player = cursor.fetchone()
    if not player:
        # Fallback create if missing
        cursor.execute("INSERT INTO player (user_id, level, xp, next_level_xp, streak, coins) VALUES (?, 1, 0, 500, 1, 0)", (user_id,))
        conn.commit()
        cursor.execute("SELECT * FROM player WHERE user_id = ?", (user_id,))
        player = cursor.fetchone()
    res = dict(player)
    conn.close()
    return res

@app.get("/")
def serve_index():
    return FileResponse("/home/ido/projects/questify-todo/index.html")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8090)
