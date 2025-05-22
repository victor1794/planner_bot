import sqlite3
import os

print("Directory", os.getcwd())


def init_db():
    conn = sqlite3.connect('tasks.db')  #Создание таблицы
    cursor = conn.cursor()
    print("DB created")
    # Таблица 1 (пользователи)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            chat_id INTEGER PRIMARY KEY,
            name TEXT,
            role TEXT
        )
    """)

    # Таблица 2 (задачи)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task TEXT,
            deadline TEXT,
            assigned_to INTEGER,
            created_by INTEGER,
            status TEXT DEFAULT 'в работе'
        )
    """)

    conn.commit()  #сохранение изменений
    conn.close()  #закрытие соединения
    print("DB closed")
