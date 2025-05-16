import os
import time
import threading
from dotenv import load_dotenv

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# === Подгружаем токен из .env ===
load_dotenv()
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]

# Хранилище учёток и прошлых значений
user_credentials = {}
last_unread = {}

def send_telegram(chat_id: str, text: str):
    import requests
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": chat_id, "text": text})

def check_messages(login: str, password: str, chat_id: str):
    options = Options()
    # options.add_argument("--headless")  # включите для невидимого режима
    driver = webdriver.Chrome(options=options)

    try:
        # 1) Логин
        driver.get("https://cabinet.nf.uust.ru")
        time.sleep(2)
        driver.find_element(By.ID, "login").send_keys(login)
        driver.find_element(By.ID, "password").send_keys(password)
        driver.find_element(By.ID, "password").send_keys(Keys.RETURN)
        time.sleep(3)

        # 2) Список конференций
        driver.get("https://cabinet.nf.uust.ru/chat/index")
        time.sleep(5)  # JS-подгрузка

        # 3) Собираем бейджи непрочитанных
        badges = driver.find_elements(By.CSS_SELECTOR,
                                      "span.badge.room-unread.pull-right")
        current = {}
        for b in badges:
            txt = b.text.strip()
            if txt.isdigit() and int(txt) > 0:
                name = b.find_element(By.XPATH, "./ancestor::a")\
                        .text.replace(txt, "").strip()
                current[name] = int(txt)

    except Exception as e:
        print(f"[{chat_id}] Ошибка при проверке: {e}")
        return
    finally:
        driver.quit()

    # 4) Сравниваем с прошлым и шлём только новые
    prev = last_unread.get(chat_id, {})
    last_unread[chat_id] = current

    # при первом запуске просто инициализируем
    if not prev:
        print(f"[{chat_id}] Инициализировано: {current}")
        return

    diffs = []
    for name, cnt in current.items():
        old = prev.get(name, 0)
        if cnt > old:
            diffs.append(f"{name}: +{cnt - old}")

    if diffs:
        send_telegram(chat_id, "🔔 Новые сообщения:\n" + "\n".join(diffs))
    else:
        print(f"[{chat_id}] Ничего нового")

# --- /start ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    await update.message.reply_text(
        f"Ваш chat_id: {cid}\n"
        "Настройка: /set <логин> <пароль>\n"
        "Пример: /set abc_d 1234"
    )

# --- /set логин пароль ---
async def set_credentials(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    cid = str(update.effective_chat.id)
    if len(args) != 2:
        return await update.message.reply_text("Используйте: /set логин пароль")
    user_credentials[cid] = (args[0], args[1])
    last_unread.pop(cid, None)
    await update.message.reply_text("Данные сохранены — проверка запущена.")

# --- Фоновая проверка ---
def background_loop():
    while True:
        for cid, creds in user_credentials.items():
            check_messages(creds[0], creds[1], cid)
        time.sleep(60)

# --- Точка входа ---
if __name__ == "__main__":
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("set", set_credentials))

    threading.Thread(target=background_loop, daemon=True).start()
    app.run_polling()