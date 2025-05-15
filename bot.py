import time
import threading
import traceback

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# === Ваш Telegram-токен ===
TELEGRAM_TOKEN = "8177925682:AAH51n-li12HXoIYF0wsNwI66xvT-h-X1uY"

# хранит логин/пароль каждого пользователя
user_credentials: dict[str, tuple[str, str]] = {}
# хранит последнее известное количество непрочитанных по каждому чату
last_unread: dict[str, dict[str, int]] = {}

def send_telegram(chat_id: str, text: str):
    import requests
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": chat_id, "text": text})

def check_messages(login: str, password: str, chat_id: str):
    options = Options()
    # раскомментируйте, чтобы видеть окно браузера:
    # options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    driver = webdriver.Chrome(options=options)

    try:
        # ——— 1) Логинимся ———
        driver.get("https://cabinet.nf.uust.ru")
        time.sleep(2)
        driver.find_element(By.ID, "login").send_keys(login)
        driver.find_element(By.ID, "password").send_keys(password)
        driver.find_element(By.ID, "password").send_keys(Keys.RETURN)
        time.sleep(3)

        # ——— 2) Открываем список конференций ———
        driver.get("https://cabinet.nf.uust.ru/chat/index")
        time.sleep(5)  # даём JS подгрузиться

        # для визуальной отладки
        driver.save_screenshot("last_check.png")

        # ——— 3) Собираем текущее количество по каждому чату ———
        badges = driver.find_elements(
            By.CSS_SELECTOR, "span.badge.room-unread.pull-right"
        )
        current: dict[str,int] = {}
        for b in badges:
            txt = b.text.strip()
            if not txt.isdigit():
                continue
            cnt = int(txt)
            if cnt > 0:
                # имя чата — текст родительского <a> без цифр
                name = (
                    b.find_element(By.XPATH, "./ancestor::a")
                     .text.replace(txt, "")
                     .strip()
                )
                current[name] = cnt

    except Exception:
        print(f"[{chat_id}] Ошибка на этапе логина/парсинга:")
        traceback.print_exc()
        driver.quit()
        return
    finally:
        # не закрываем до после формирования current
        pass

    driver.quit()

    # ——— 4) Сравниваем с предыдущим состоянием ———
    prev = last_unread.get(chat_id)
    last_unread[chat_id] = current  # обновляем состояние

    if prev is None:
        # первый запуск для этого пользователя — просто инициализируем
        print(f"[{chat_id}] Инициализировано состояние: {current}")
        return

    # находим только те чаты, где число выросло
    new_msgs: list[str] = []
    for name, cnt in current.items():
        old = prev.get(name, 0)
        if cnt > old:
            diff = cnt - old
            new_msgs.append(f"{name}: +{diff}")

    if new_msgs:
        send_telegram(chat_id,
            f"🔔 Новые сообщения:\n" + "\n".join(new_msgs)
        )
    else:
        print(f"[{chat_id}] Новых сообщений нет")

# ——— Команда /start ———
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    await update.message.reply_text(
        f"Ваш chat_id: {cid}\n"
        "Чтобы настроить бота, отправьте:\n"
        "/set <логин> <пароль>\n"
        "Пример: /set agf_m 3651"
    )

# ——— Команда /set ———
async def set_credentials(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    cid = str(update.effective_chat.id)
    if len(args) != 2:
        await update.message.reply_text("Используйте: /set логин пароль")
        return
    user_credentials[cid] = (args[0], args[1])
    last_unread.pop(cid, None)  # сбросим старое состояние
    await update.message.reply_text("Данные сохранены! Проверка запущена.")

# ——— Фоновая проверка ———
def background_loop():
    while True:
        for cid, (login, pwd) in user_credentials.items():
            check_messages(login, pwd, cid)
        time.sleep(60)

# ——— Точка входа ———
if __name__ == "__main__":
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("set", set_credentials))

    threading.Thread(target=background_loop, daemon=True).start()
    app.run_polling()