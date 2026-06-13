FROM python:3.12-slim

# Avoid buffering so logs show up immediately
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies first for better layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the bot source code
COPY bot.py .

# SQLite DB will be created here at runtime; mount a volume to persist it
VOLUME ["/app/data"]
ENV DB_FILE=/app/data/bot_data.db

# Pass your bot token in at runtime instead of hardcoding it:
#   docker run -e TELEGRAM_BOT_TOKEN=xxxx ...
ENV TELEGRAM_BOT_TOKEN=""

CMD ["python", "bot.py"]