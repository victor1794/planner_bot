from cfg import TOKEN
import telebot
from telebot import types
import sqlite3
import database
from datetime import datetime

bot = telebot.TeleBot(TOKEN)  #привязка к токену
# Подключаем БД
conn = sqlite3.connect('tasks.db', check_same_thread=False)
cursor = conn.cursor()
temp_employees_list = []  # Глобальная переменная для хранения списка сотрудников на время выбора
database.init_db()


#обработка команды /start добавление пользователя
@bot.message_handler(commands=['start'])
def start(message):
    # Проверяем, есть ли уже пользователь в БД
    cursor.execute("SELECT role FROM users WHERE chat_id = ?", (message.chat.id,))
    user = cursor.fetchone()

    if user:
        bot.reply_to(message, f"Вы уже зарегистрированы как {user[0]}")
        return

    # Предлагаем выбрать роль
    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True)
    markup.add(types.KeyboardButton("Я руководитель"), types.KeyboardButton("Я сотрудник"))
    bot.send_message(message.chat.id, "Выберите вашу роль:", reply_markup=markup)
    bot.register_next_step_handler(message, process_role_selection)

def process_role_selection(message):
    role = message.text.lower()

    if role == "я руководитель":
        handle_leader_selection(message)
    elif role == "я сотрудник":
        handle_employee_selection(message)
    else:
        bot.reply_to(message, "Неверный выбор. Попробуйте снова.")
        bot.register_next_step_handler(message, process_role_selection)

#добавление если руководитель
def handle_leader_selection(message):
    existing_leader = get_leader()

    if existing_leader:
        bot.send_message(message.chat.id, f"⚠️ Руководитель уже существует: {existing_leader[1]}.\n" 
                                                "Обратитесь к нему для обновления данных.")

    else:
        bot.send_message(message.chat.id, "Введите ваше имя и фамилию:")
        bot.register_next_step_handler(message, lambda m: complete_registration(m, role="руководитель"))

#добавление если сотрудник
def handle_employee_selection(message):
    bot.send_message(message.chat.id, "Введите ваше имя и фамилию:")
    bot.register_next_step_handler(message, lambda m: send_leader_new_employee_request(m.text.strip(), m.chat.id))

#добавление пользователя в бд
def add_user(chat_id, name, role):
    cursor.execute("INSERT INTO users (chat_id, name, role) VALUES (?, ?, ?)", (chat_id, name, role))
    conn.commit()

#регистрация пользователя (с именем и фамилией)
def complete_registration(message, role):
    full_name = message.text.strip()
    chat_id = message.chat.id

    add_user(chat_id, full_name, role)
    bot.send_message(message.chat.id, f"Вы зарегистрировались как {role} — {full_name}")

    if role == "руководитель":
        bot.send_message(message.chat.id, "Теперь вы можете управлять списком сотрудников.")

    elif role == "сотрудник":
        bot.send_message(message.chat.id, "Вы добавлены как сотрудник")



#запрос руководителю о добавлении сотрудника
def send_leader_new_employee_request(name, chat_id):
    leader = get_leader()

    if not leader:
        bot.send_message(chat_id, "Ошибка: руководитель ещё не назначен.")
        return

    markup = types.InlineKeyboardMarkup()
    btn_approve = types.InlineKeyboardButton("✅ Добавить", callback_data=f"approve_{chat_id}_{name}")
    btn_reject = types.InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{chat_id}_{name}")
    markup.row(btn_approve, btn_reject)

    bot.send_message(leader[0], f"Новый сотрудник хочет присоединиться:\n{name}\nПринять?", reply_markup=markup)
    bot.send_message(chat_id, "Запрос отправлен руководителю. Ждём подтверждения...")

#обработка запроса
@bot.callback_query_handler(func=lambda call: call.data.startswith("approve_") or call.data.startswith("reject_"))
def handle_callback(call):
    _, emp_chat_id, emp_name = call.data.split("_", 2)

    if call.from_user.id != get_leader()[0]:
        bot.answer_callback_query(call.id, "Вы не являетесь руководителем.")
        return

    if call.data.startswith("approve_"):
        add_user(emp_chat_id, emp_name, "сотрудник")
        bot.send_message(emp_chat_id, f"✅ Вы добавлены в коллектив как {emp_name}")
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                              text=f"Сотрудник {emp_name} добавлен в базу.")
    else:
        bot.send_message(emp_chat_id, "❌ Ваш запрос отклонён.")
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                              text=f"Запрос от {emp_name} отклонён.")


@bot.message_handler(commands=['id'])
def get_id(message):
    bot.reply_to(message, f"Ваш chat_id: {message.chat.id}")

@bot.message_handler(commands=['employees'])
def show_employees(message):
    try:
        # Получаем список всех пользователей из БД
        cursor.execute("SELECT name, role FROM users")
        users = cursor.fetchall()

        if not users:
            bot.reply_to(message, "Список сотрудников пуст.")
            return

        # Формируем красивый вывод
        output = "Сотрудники:\n"
        for idx, (name, role) in enumerate(users, start=1):
            output += f"{idx}. {name} — {role}\n"

        bot.send_message(message.chat.id, output)

    except Exception as e:
        bot.send_message(message.chat.id, f"Ошибка при получении списка: {e}")


# Обработка команды /help
@bot.message_handler(commands=['help'])
def send_help(message):
    help_text = (
        "/start — начать диалог\n"
        "/help — список комманд\n"
        "/add_task — добавить задачу\n"
        "/employees - список сотрудников\n"
        "/delete_employees - удалить сотрудников\n"
        "/id - уникальный id диалога\n"
        "/my_tasks - мои задачи\n"
    )
    bot.reply_to(message, help_text)

#проверка на руководителя
def is_leader(chat_id):
    cursor.execute("SELECT role FROM users WHERE chat_id = ?", (chat_id,))
    result = cursor.fetchone()
    return result and result[0] == 'руководитель'

#проверка на сотрудника
def is_employee(chat_id):
    cursor.execute("SELECT role FROM users WHERE chat_id = ?", (chat_id,))
    result = cursor.fetchone()
    return result and result[0] == 'сотрудник'

def get_leader():
    cursor.execute("SELECT chat_id, name FROM users WHERE role = 'руководитель'")
    return cursor.fetchone()


# список работяг
def get_employees():
    cursor.execute("SELECT chat_id, name, role FROM users WHERE role = 'сотрудник'")
    return cursor.fetchall()


# команда add task добавление задачи
@bot.message_handler(commands=['add_task'])
def add_task(message):
    if is_leader(message.chat.id):  # только руководителю доступно
        global temp_employees_list
        temp_employees_list = get_employees()  # текущее состояние бд
        if temp_employees_list:
            # список сотрудников с номерами
            output = "Выберите номер сотрудника:\n"
            for idx, emp in enumerate(temp_employees_list, start=1):
                output += f"{idx}. {emp[1]} ({emp[2]})\n"  # 1 имя 2 роль

            bot.send_message(message.chat.id, output)
            bot.register_next_step_handler(message, process_employee_number)
        else:
            bot.send_message(message.chat.id, "Нет доступных сотрудников для назначения задачи")
    else:
        bot.reply_to(message, "У вас нет прав на эту команду.")


# выбор сотрудника номером
def process_employee_number(message):
    try:
        selected_index = int(message.text) - 1  # номер сотрудника - 1 этоиндекс в списке сотрудников
        global temp_employees_list

        if 0 <= selected_index < len(temp_employees_list):
            selected_emp = temp_employees_list[selected_index]
            selected_name = selected_emp[1]

            bot.send_message(message.chat.id, f"Вы выбрали: {selected_name} \n Введите задачу:")


            bot.register_next_step_handler(message, lambda m: process_task_input(m, selected_emp[0], selected_name))
        else:
            bot.send_message(message.chat.id, "Неверный номер. Попробуйте снова:")
            bot.register_next_step_handler(message, process_employee_number)

    except ValueError:
        bot.send_message(message.chat.id, "Пожалуйста, введите только номер сотрудника.")
        bot.register_next_step_handler(message, process_employee_number)


# ввод задачи
def process_task_input(message, employee_id, employee_name):
    task = message.text
    bot.send_message(message.chat.id, f"Теперь укажите дедлайн для '{task}' в формате ддммгггг:")
    bot.register_next_step_handler(message, lambda m: process_deadline_input(m, task, employee_id, employee_name))


#проверка валидности даты тип дд мм гг

def is_valid_date(date_text):
    try:
        datetime.strptime(date_text, '%d.%m.%Y')
        return True
    except ValueError:
        return False

#проверка дедлайн не раньше сегодняшнего дня
def is_future_date(date_text):
    try:
        input_date = datetime.strptime(date_text, "%d.%m.%Y")
        today = datetime.strptime(str(datetime.now()).split(' ')[0], "%Y-%m-%d")
        print(input_date)
        print(today)
        return input_date >= today
    except ValueError:
        return False

# ввод дэда
def process_deadline_input(message, task, employee_id, employee_name):
    deadline = message.text.strip()

    if not is_valid_date(deadline):
        bot.send_message(message.chat.id, "Неверный формат даты. Используйте ддммгггг")
        bot.register_next_step_handler(message, lambda m: process_deadline_input(m, task, employee_id, employee_name))
        return
    if not is_future_date(deadline):
        bot.send_message(message.chat.id, "дедлайн не может быть раньше сегодняшнего дня.")
        bot.register_next_step_handler(message, lambda m: process_deadline_input(m, task, employee_id, employee_name))
        return

    # Сохраняем задачу в БД

    cursor.execute("""
                INSERT INTO tasks (task, deadline, assigned_to, created_by)
                VALUES (?, ?, ?, ?)
            """, (task, deadline, employee_id, message.chat.id))
    conn.commit()


    # увед сотруднику
    try:
        if datetime.strptime(str(datetime.now()).split(' ')[0], "%Y-%m-%d") == datetime.strptime(deadline, "%d.%m.%Y"):
            bot.send_message(employee_id, f"Вам назначена новая задача!\n"
                                          f"Задача: {task}\n"
                                          f"До конца сегодняшнего дня")
        else:
            bot.send_message(employee_id, f"Вам назначена новая задача!\n"
                                          f"Задача: {task}\n"
                                          f"До: {deadline}\n")
        bot.send_message(message.chat.id, f"Задача '{task}' назначена {employee_name}.")


    except Exception as e:
        bot.send_message(message.chat.id, "Не удалось отправить сообщение сотруднику")


@bot.message_handler(commands=['delete_employees'])
def delete_employee(message):
    if not is_leader(message.chat.id):
        bot.reply_to(message, "❌ У вас нет прав на удаление сотрудников.")
        return

    employees = get_employees()

    if not employees:
        bot.reply_to(message, "Нет доступных сотрудников для удаления.")
        return

    output = "Выберите номер сотрудника для удаления:\n"
    for idx, emp in enumerate(employees, start=1):
        output += f"{idx}. {emp[1]}\n"

    bot.send_message(message.chat.id, output)
    bot.register_next_step_handler(message, process_delete_employee_selection, employees)

def process_delete_employee_selection(message, employees):
    try:
        selected_index = int(message.text) - 1

        if 0 <= selected_index < len(employees):
            selected_emp = employees[selected_index]
            emp_chat_id = selected_emp[0]
            emp_name = selected_emp[1]

            # Удаляем сотрудника из БД
            cursor.execute("DELETE FROM users WHERE chat_id = ?", (emp_chat_id,))
            conn.commit()

            bot.send_message(message.chat.id, f"✅ Сотрудник {emp_name} удален.")
            bot.send_message(emp_chat_id, "⚠️ Вы удалены из коллектива.")

        else:
            bot.send_message(message.chat.id, "❌ Неверный номер сотрудника.")
    except ValueError:
        bot.send_message(message.chat.id, "Введите только номер сотрудника.")
        bot.register_next_step_handler(message, process_delete_employee_selection, employees)




#получение задач
def get_tasks_for_user(chat_id):
    cursor.execute("SELECT id, task, deadline FROM tasks WHERE assigned_to = ?", (chat_id,))
    return cursor.fetchall()

@bot.message_handler(commands=['my_tasks'])
def show_my_tasks(message):
    chat_id = message.chat.id

    if not is_employee(chat_id) and not is_leader(chat_id):
        bot.reply_to(message, "Вы не добавлены в систему.")
        return

    tasks = get_tasks_for_user(chat_id)

    if not tasks:
        bot.reply_to(message, "У вас нет задач.")
        return

    output = "Ваши задачи:\n"
    for idx, (task_id, task_text, deadline) in enumerate(tasks, start=1):
        output += f"{idx}. [ID {task_id}] {task_text}\n"
        output += f"   Дедлайн: {deadline}\n"

    bot.send_message(chat_id, output)


@bot.message_handler(commands=['finish_task'])
def finish_task(message):
    chat_id = message.chat.id

    # Проверяем, является ли пользователь сотрудником
    if not is_employee(chat_id):
        bot.reply_to(message, "Вы не сотрудник.")
        return

    tasks = get_tasks_for_user(chat_id)

    if not tasks:
        bot.reply_to(message, "У вас нет активных задач.")
        return

    output = "Выберите номер задачи для завершения:\n"
    for idx, (task_id, task_text, deadline) in enumerate(tasks, start=1):
        output += f"{idx}. {task_text} (до {deadline})\n"

    bot.send_message(chat_id, output)
    bot.register_next_step_handler(message, process_finish_task_selection, tasks)

def process_finish_task_selection(message, tasks):
    try:
        selected_index = int(message.text) - 1

        if 0 <= selected_index < len(tasks):
            selected_task = tasks[selected_index]
            task_id, task_text, deadline = selected_task

            # Удаляем задачу из БД
            cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            conn.commit()

            # Получаем имя сотрудника
            cursor.execute("SELECT name FROM users WHERE chat_id = ?", (message.chat.id,))
            emp_name = cursor.fetchone()[0]

            # Находим руководителя
            leader = get_leader()

            # Отправляем сообщение руководителю
            if leader:
                bot.send_message(leader[0], f"✅ Задача выполнена!\n"
                                           f"Сотрудник: {emp_name}\n"
                                           f"Задача: {task_text}")
            # Сообщение сотруднику
            bot.send_message(message.chat.id, f"Задача '{task_text}' отмечена как выполненная.")
        else:
            bot.send_message(message.chat.id, "❌ Неверный номер задачи.")
    except ValueError:
        bot.send_message(message.chat.id, "Введите только номер задачи.")
        bot.register_next_step_handler(message, process_finish_task_selection, tasks)

#дэфолт
@bot.message_handler(func=lambda message: True)
def echo_all(message):
    bot.reply_to(message, f" Неправильный ввод/нет такой комманды")

# запуск
print("Бот запущен...")
bot.polling(none_stop=True)

