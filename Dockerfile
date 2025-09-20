FROM python:3.11-slim
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# файлы приложения
COPY app.py .
COPY static ./static

# необязательно: добавь свои таблицы в образ (если хочешь использовать маппинг из txt)
# COPY data ./data

EXPOSE 400
CMD ["uvicorn","app:app","--host","0.0.0.0","--port","400","--proxy-headers"]
