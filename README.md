Быстрый старт (Docker)
# 1) Собрать образ
docker build -t zr_plus-spectrum-calculator:latest .

# 2) Запустить контейнер на порту 400
docker run -d --name zr_plus-spectrum-calculator \
  -p 400:400 \
  -v $(pwd)/static:/app/static:ro \
  -v $(pwd)/data:/app/data:ro \
  --restart unless-stopped \
  zr_plus-spectrum-calculator:latest

# 3) Проверить
curl -s http://127.0.0.1:400/healthz   # {"ok": true}
