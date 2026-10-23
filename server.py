import sqlite3
from fastapi import FastAPI, HTTPException
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
        CREATE TABLE IF NOT EXISTS quests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
            id INTEGER PRIMARY KEY,
            level INTEGER NOT NULL,
            xp INTEGER NOT NULL,
            next_level_xp INTEGER NOT NULL,
            streak INTEGER NOT NULL,
            coins INTEGER NOT NULL
        )
    """)
    # Seed default player if empty
    cursor.execute("SELECT COUNT(*) FROM player")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO player (id, level, xp, next_level_xp, streak, coins) VALUES (1, 3, 240, 500, 5, 120)")
    
    # Seed default quests if empty
    cursor.execute("SELECT COUNT(*) FROM quests")
    if cursor.fetchone()[0] == 0:
        default_quests = [
            ("לפתח אבטיפוס ראשוני לאפליקציה", "epic", "high", 150, False, "פיתוח"),
            ("סידור שולחן עבודה וניקיון מייל", "daily", "low", 30, True, "ארגון"),
            ("קריאת פרק בספר מקצועי", "side", "medium", 50, False, "למידה")
        ]
        cursor.executemany("INSERT INTO quests (title, type, energy, xp, completed, category) VALUES (?, ?, ?, ?, ?, ?)", default_quests)
    
    conn.commit()
    conn.close()

init_db()

class QuestCreate(BaseModel):
    title: str
    type: str
    energy: str
    xp: int
    category: str

@app.get("/api/quests")
def get_quests():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM quests ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

@app.post("/api/quests")
def add_quest(quest: QuestCreate):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO quests (title, type, energy, xp, completed, category) VALUES (?, ?, ?, ?, ?, ?)",
        (quest.title, quest.type, quest.energy, quest.xp, False, quest.category)
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
    
    new_completed = 0 if quest["completed"] else 1
    cursor.execute("UPDATE quests SET completed = ? WHERE id = ?", (new_completed, quest_id))
    
    # Update player XP
    cursor.execute("SELECT * FROM player WHERE id = 1")
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

    cursor.execute("UPDATE player SET level = ?, xp = ?, next_level_xp = ?, coins = ? WHERE id = 1", (p_level, p_xp, p_next, p_coins))
    conn.commit()
    conn.close()
    return {"status": "updated", "completed": bool(new_completed)}

@app.get("/api/player")
def get_player():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM player WHERE id = 1")
    player = dict(cursor.fetchone())
    conn.close()
    return player

@app.get("/")
def serve_index():
    return FileResponse("/home/ido/projects/questify-todo/index.html")
