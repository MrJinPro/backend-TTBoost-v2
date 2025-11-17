# TTBoost Backend v2 — Продакшн-развертывание (api.ttboost.pro + media.ttboost.pro)

Бэкенд предоставляет два слоя API:

- **v1** — устаревшие лицензии (для старых мобильных клиентов, сохранено для обратной совместимости)
- **v2** — основная авторизация (логин = TikTok username + пароль), лицензии через обмен (redeem), хранение в PostgreSQL, медиадомен.

Документ описывает полный цикл: подготовка сервера, деплой, обновление, тестирование, резервное копирование и выпуск лицензий.

---
## 1. Требования окружения

| Компонент | Рекомендация |
|-----------|--------------|
| ОС | Ubuntu 22.04 LTS / Debian 12 |
| Python | 3.10–3.12 |
| БД | PostgreSQL 14+ (можно начать с SQLite и быстро перейти) |
| Reverse Proxy | Nginx (TLS, gzip) |
| FFmpeg | Не обязателен, но полезен для будущей обработки аудио |
| Дополнительно | systemd для автостарта, logrotate для логов |

Порты: Uvicorn internal (127.0.0.1:8000/8001), внешние 80/443 на Nginx.

---
## 2. Структура каталогов на сервере

```bash
/opt/ttboost/          # корень приложения (git clone)
    backend/             # код бэкенда
    .venv/               # виртуальное окружение Python
/var/ttboost/media/    # MEDIA_ROOT (звуки, TTS, пользовательские файлы)
/var/log/ttboost/      # логи (uvicorn, nginx дополнительно)
```

Создайте каталоги:
```bash
sudo mkdir -p /var/ttboost/media /var/log/ttboost
sudo chown -R www-data:www-data /var/ttboost/media
sudo chown -R www-data:www-data /var/log/ttboost
```

---
## 3. Установка кода и зависимостей

```bash
cd /opt
sudo git clone <PRIVATE_REPO_URL> ttboost
cd ttboost/backend
python3 -m venv ../.venv
source ../.venv/bin/activate
pip install -U pip
pip install -r requirements.txt
```

Проверка импорта:
```bash
python -c "import app.main; print('OK')"
```

---
## 4. Настройка PostgreSQL (пример)

```bash
sudo -u postgres psql <<'SQL'
CREATE USER ttboost WITH PASSWORD 'STRONG_DB_PASS';
CREATE DATABASE ttboost OWNER ttboost;
GRANT ALL PRIVILEGES ON DATABASE ttboost TO ttboost;
SQL
```

Проверьте подключение:
```bash
psql 'postgresql://ttboost:STRONG_DB_PASS@localhost:5432/ttboost' -c '\dt'
```

DATABASE_URL формат: `postgresql+psycopg://ttboost:STRONG_DB_PASS@localhost:5432/ttboost`.

---
## 5. Переменные окружения (.env)

Скопируйте `backend/.env.example` → `.env` и задайте:

```
ENV=prod
SERVER_HOST=https://api.ttboost.pro
MEDIA_BASE_URL=https://media.ttboost.pro
MEDIA_ROOT=/var/ttboost/media
JWT_SECRET=<случайный_256бит_ключ>
ACCESS_TTL_MIN=1440
DATABASE_URL=postgresql+psycopg://ttboost:STRONG_DB_PASS@localhost:5432/ttboost
ADMIN_API_KEY=<секрет_для_выдачи_лицензий>
SIGN_API_KEY=<optional>
SIGN_SERVER_URL=<optional>
TTS_BASE_URL=https://media.ttboost.pro
```

Генерация секрета:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

---
## 6. Инициализация БД

При первом запуске `init_db()` создаст таблицы автоматически. Alembic можно добавить позже:
```bash
source ../.venv/bin/activate
python -c "from app.db.database import init_db; init_db(); print('DB ready')" -m app.main
```

---
## 7. Запуск (ручной тест)

```bash
source ../.venv/bin/activate
cd backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

Проверка:
```bash
curl -s http://127.0.0.1:8001/ | jq
```

---
## 8. systemd unit (prod)

`/etc/systemd/system/ttboost.service`:
```
[Unit]
Description=TTBoost FastAPI Service
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/ttboost/backend
Environment="PYTHONUNBUFFERED=1"
EnvironmentFile=/opt/ttboost/backend/.env
ExecStart=/opt/ttboost/.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 2
Restart=always
RestartSec=5
StandardOutput=append:/var/log/ttboost/uvicorn.out.log
StandardError=append:/var/log/ttboost/uvicorn.err.log

[Install]
WantedBy=multi-user.target
```

Применение:
```bash
sudo systemctl daemon-reload
sudo systemctl enable ttboost --now
sudo systemctl status ttboost
tail -f /var/log/ttboost/uvicorn.out.log
```

---
## 9. Nginx конфигурация

`/etc/nginx/sites-available/ttboost.conf` (ссылку в sites-enabled):
```
server {
        server_name api.ttboost.pro;
        listen 80;
        listen 443 ssl;
        # ssl_certificate /etc/letsencrypt/live/api.ttboost.pro/fullchain.pem;
        # ssl_certificate_key /etc/letsencrypt/live/api.ttboost.pro/privkey.pem;

        client_max_body_size 5M; # ограничение на аплоад звуков

        location / {
                proxy_pass http://127.0.0.1:8000;
                proxy_set_header Host $host;
                proxy_set_header X-Real-IP $remote_addr;
                proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
                proxy_set_header X-Forwarded-Proto $scheme;
                proxy_read_timeout 300;
                # WebSocket
                proxy_set_header Upgrade $http_upgrade;
                proxy_set_header Connection "upgrade";
        }
}

server {
        server_name media.ttboost.pro;
        listen 80;
        listen 443 ssl;
        # ssl_certificate /etc/letsencrypt/live/media.ttboost.pro/fullchain.pem;
        # ssl_certificate_key /etc/letsencrypt/live/media.ttboost.pro/privkey.pem;

        location /static/ {
                alias /var/ttboost/media/; # /static/ -> /var/ttboost/media/
                add_header Access-Control-Allow-Origin *;
                access_log off;
                expires 30d;
        }
}
```

Тест и перезагрузка:
```bash
sudo nginx -t && sudo systemctl reload nginx
```

---
## 10. Основные v2 эндпоинты

Авторизация и лицензии:
| Метод | Путь | Назначение |
|-------|------|-----------|
| POST | /v2/auth/register | Регистрация без лицензии (можно ограничить) |
| POST | /v2/auth/login | Логин по username+password |
| POST | /v2/auth/redeem-license | Обмен license_key на JWT, привязка к пользователю |
| GET  | /v2/auth/me | Профиль и настройки |
| POST | /v2/license/issue | Выдача ключа (требует Admin-Api-Key) |
| GET  | /v2/license/check?key=... | Проверка статуса лицензии |

Функционал:
- POST /v2/settings/update
- POST /v2/sounds/upload / GET /v2/sounds/list
- POST /v2/triggers/set / GET /v2/triggers/list / POST /v2/triggers/delete
- WS /v2/ws — события (chat, gift, like, join, follow, subscribe)

WebSocket авторизация:
- В мобильных клиентах: заголовок `Authorization: Bearer <JWT>`
- В браузере: `wss://api.ttboost.pro/v2/ws?token=<JWT>` (query fallback)

---
## 11. Медиа и ограничения

- Пути: `/static/tts/<user_id>/...`, `/static/sounds/<user_id>/...`
- Размер файла: ≤100 KB
- Длительность: ≤5 секунд (mutagen)
- Генерация TTS: gTTS / Edge-TTS (фоллбек)
- Абсолютные URL: строятся из `MEDIA_BASE_URL`

---
## 12. Безопасность

- Пароли: **pbkdf2_sha256** (passlib) — без проблем сборки под Windows/Linux
- JWT: HS256, TTL настраивается `ACCESS_TTL_MIN` (по умолчанию 1440 минут)
- Лицензии: статус/срок хранится в таблице `license_keys`, привязка `user_id` после redeem
- Admin-Api-Key: секрет для выдачи лицензий, хранить только в продакшн .env
- Резервное копирование БД: `pg_dump ttboost > /backup/ttboost_$(date +%F).sql`

Рекомендации:
- Ограничить публичный доступ к /v2/auth/register (например через firewall или отключить для продакшна)
- Логи и пароли не хранить в публичных местах

---
## 13. Обновление приложения

```bash
cd /opt/ttboost
sudo -u www-data git pull
source .venv/bin/activate
pip install -r backend/requirements.txt --upgrade
sudo systemctl restart ttboost
sudo systemctl status ttboost
```

Проверка здоровья:
```bash
curl -s https://api.ttboost.pro/ | jq
```

---
## 14. Базовый сценарий тестирования после деплоя

```bash
# Выдать лицензию (админ)
curl -X POST https://api.ttboost.pro/v2/license/issue \
    -H "Admin-Api-Key: <ADMIN_API_KEY>" \
    -H "Content-Type: application/json" \
    -d '{"plan":"pro","ttl_days":7}'

# Redeem (получить JWT)
curl -X POST https://api.ttboost.pro/v2/auth/redeem-license \
    -H "Content-Type: application/json" \
    -d '{"username":"testuser","password":"StrongPass123","license_key":"TTB-XXXX-XXXX-XXXX"}'

# Проверить профиль
curl -H "Authorization: Bearer <JWT>" https://api.ttboost.pro/v2/auth/me | jq
```

WebSocket (быстрый smoke через wscat):
```bash
wscat -c "wss://api.ttboost.pro/v2/ws?token=<JWT>"
```

---
## 15. Логи и мониторинг

- Uvicorn: `/var/log/ttboost/uvicorn.out.log`, `/var/log/ttboost/uvicorn.err.log`
- Nginx: `/var/log/nginx/access.log`, `/var/log/nginx/error.log`
- Рекомендация: настроить fail2ban и базовый мониторинг (Prometheus Node Exporter, Grafana)

---
## 16. Миграции схемы

Пока используется автосоздание через SQLAlchemy. Для изменений:
```bash
pip install alembic
alembic init alembic
# настроить sqlalchemy.url в alembic.ini
alembic revision --autogenerate -m "add new table"
alembic upgrade head
```

---
## 17. Совместимость с v1

Старые клиенты продолжают использовать `/auth/login` (лицензия). Новые — поток `redeem-license` + `login`. Плавная миграция: сначала внедрить выдачу ключей, затем принудительный переход.

---
## 18. Типичные проблемы

| Симптом | Причина | Решение |
|---------|---------|---------|
| 401 на /v2/ws | Неверный или отсутствует токен | Передать ?token=<JWT> или заголовок Authorization |
| UserNotFoundError в TikTokLive | Неверный username или стрим оффлайн | Проверить что стрим идёт и ник указан без @ |
| 413 Request Entity Too Large | Большой файл | Уменьшить размер (<100KB) и длительность (<5s) |
| Лицензия 409 при redeem | Уже привязана другому пользователю | Использовать исходный аккаунт или выдать новую лицензию |

---
## 19. Быстрый чек-лист перед релизом

- [ ] Работает `/` health
- [ ] Выдача лицензии (issue) OK
- [ ] Redeem + login OK
- [ ] WebSocket подключение получает события (на реальном стриме)
- [ ] Загрузки звуков (<100KB) проходят
- [ ] MEDIA_BASE_URL возвращает доступные файлы
- [ ] Логи без повторяющихся ошибок
- [ ] TLS сертификаты действительны
- [ ] Резервная копия БД сделана

---
**Версия инструкции:** 2.0  
**Последнее обновление:** 16.11.2025
