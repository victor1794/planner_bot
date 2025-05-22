import sqlite3

# Подключение к бд
conn = sqlite3.connect('tasks.db')
cursor = conn.cursor()

# Вывод users
cursor.execute("SELECT * FROM users")
users = cursor.fetchall()
print("Пользователи:")
for user in users:
    print(user)

# вывод задач
cursor.execute("SELECT * FROM tasks")
tasks = cursor.fetchall()
print("\nЗадачи:")
for task in tasks:
    print(task)