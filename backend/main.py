from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from typing import Optional
from decimal import Decimal
import sqlite3
from datetime import datetime

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # allow all origins
    allow_credentials=False,  # IMPORTANT: set False
    allow_methods=["*"],
    allow_headers=["*"],
)


# Database
conn = sqlite3.connect("expenses.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS expenses (
    id INTEGER PRIMARY KEY,
    amount TEXT,
    category TEXT,
    description TEXT,
    date TEXT,
    created_at TEXT,
    idem_key TEXT UNIQUE
)
""")
conn.commit()


class Expense(BaseModel):
    amount: Decimal
    category: str
    description: str
    date: str


@app.post("/expenses")
def add_expense(
    expense: Expense,
    idempotency_key: Optional[str] = Header(None)
):
    if not idempotency_key:
        raise HTTPException(400, "Missing Idempotency-Key")

    now = datetime.utcnow().isoformat()

    try:
        cursor.execute("""
        INSERT INTO expenses
        (amount, category, description, date, created_at, idem_key)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (
            str(expense.amount),
            expense.category,
            expense.description,
            expense.date,
            now,
            idempotency_key
        ))
        conn.commit()

    except sqlite3.IntegrityError:
        return {"message": "Already processed"}

    return {"message": "Expense added"}

@app.delete("/expenses/{expense_id}")
def delete_expense(expense_id: int):
    cursor.execute("DELETE FROM expenses WHERE id=?", (expense_id,))
    conn.commit()

    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Expense not found")

    return {"message": "Expense deleted successfully"}

@app.put("/expenses/{expense_id}")
def update_expense(expense_id: int, expense: Expense):
    cursor.execute("SELECT * FROM expenses WHERE id=?", (expense_id,))
    existing = cursor.fetchone()

    if not existing:
        raise HTTPException(status_code=404, detail="Expense not found")

    cursor.execute("""
        UPDATE expenses
        SET amount=?, category=?, description=?, date=?
        WHERE id=?
    """, (
        str(expense.amount),
        expense.category,
        expense.description,
        expense.date,
        expense_id
    ))

    conn.commit()

    return {"message": "Expense updated successfully"}

@app.get("/expenses/total")
def get_total_expense():
    rows = cursor.execute("SELECT amount FROM expenses").fetchall()

    total = sum(Decimal(row[0]) for row in rows)

    return {"total": total}


@app.get("/expenses")
def get_expenses(
    category: Optional[str] = None,
    sort_date_desc: Optional[bool] = False
):
    query = "SELECT * FROM expenses"
    params = []

    if category:
        query += " WHERE category=?"
        params.append(category)

    if sort_date_desc:
        query += " ORDER BY date DESC"

    rows = cursor.execute(query, params).fetchall()

    data = []

    for r in rows:
        data.append({
            "id": r[0],
            "amount": r[1],
            "category": r[2],
            "description": r[3],
            "date": r[4],
            "created_at": r[5]
        })

    return data
