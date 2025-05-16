# 1) Берём лёгкий образ с Python 3.11
FROM python:3.11-slim

# 2) Устанавливаем Chromium и драйвер
RUN apt-get update && apt-get install -y \
    chromium chromium-driver \
 && rm -rf /var/lib/apt/lists/*

# 3) Переходим в рабочую директорию
WORKDIR /app

# 4) Копируем список зависимостей и устанавливаем их
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5) Копируем весь код бота
COPY . .

# 6) Указываем, где лежат бинарники хрома
ENV CHROME_BIN=/usr/bin/chromium
ENV CHROME_DRIVER=/usr/bin/chromedriver

# 7) Запускаем скрипт
CMD ["python", "bot.py"]
