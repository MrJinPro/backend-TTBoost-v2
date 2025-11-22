# TTBoost Backend v2 — Production Checklist

## ✅ Деплой завершён: 18.11.2025

API: https://api.ttboost.pro  
Media: https://media.ttboost.pro  
Статус: **PROD READY**

---

## 🔍 Быстрая проверка (POST-DEPLOY)

### 1. Health Check
```bash
curl -s https://api.ttboost.pro/ | jq
```
Ожидаемый ответ:
```json
{
  "status": "ok",
  "service": "ttboost-backend",
  "env": "prod",
  "server_host": "https://api.ttboost.pro",
  "tts_base_url": "https://media.ttboost.pro"
}
```
✅ **Работает**

---

## 🧪 Тестирование основных функций

### 2. Выдача лицензии (Admin)
```bash
curl -X POST https://api.ttboost.pro/v2/license/issue \
  -H "Admin-Api-Key: <YOUR_ADMIN_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"plan":"pro","ttl_days":30}' | jq
```
Ожидаемый ответ:
```json
{
  "key": "TTB-XXXX-XXXX-XXXX",
  "plan": "pro",
  "expires_at": "2025-12-18T..."
}
```

### 3. Обмен лицензии на JWT (redeem)
```bash
curl -X POST https://api.ttboost.pro/v2/auth/redeem-license \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "password": "SecurePass123!",
    "license_key": "TTB-XXXX-XXXX-XXXX"
  }' | jq
```
Ожидаемый ответ:
```json
{
  "access_token": "eyJhbGc...",
  "token_type": "bearer",
  "license_expires_at": "2025-12-18T...",
  "plan": "pro"
}
```

### 4. Проверка профиля (Bearer auth)
```bash
TOKEN="<your_jwt_token>"
curl -H "Authorization: Bearer $TOKEN" \
  https://api.ttboost.pro/v2/auth/me | jq
```
Ожидаемый ответ:
```json
{
  "id": "uuid",
  "username": "testuser",
  "voice_id": "ru-RU-SvetlanaNeural",
  "tts_enabled": true,
  "gift_sounds_enabled": true,
  "tts_volume": 100,
  "gifts_volume": 100
}
```

### 5. Загрузка звука
```bash
TOKEN="<your_jwt_token>"
curl -X POST https://api.ttboost.pro/v2/sounds/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@test_sound.mp3" | jq
```
Проверка:
- Размер файла ≤ 100 KB
- Длительность ≤ 5 секунд
- URL возвращается с `https://media.ttboost.pro/static/sounds/...`

### 6. Установка триггера
```bash
TOKEN="<your_jwt_token>"
curl -X POST https://api.ttboost.pro/v2/triggers/set \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "gift",
    "condition_key": "gift_name",
    "condition_value": "Rose",
    "action": "play_sound",
    "action_params": {"sound_filename": "rose_sound.mp3"}
  }' | jq
```

### 7. WebSocket подключение (web)
```bash
# Установить wscat: npm install -g wscat
wscat -c "wss://api.ttboost.pro/v2/ws?token=<your_jwt_token>"
```
Ожидается:
- Успешное подключение
- Если TikTok username задан и стрим идёт → события приходят
- Если стрим оффлайн → соединение остаётся открытым, но событий нет

---

## 📋 Контрольный список функций

### Авторизация
- [ ] POST /v2/license/issue (админ) → выдаёт ключ
- [ ] POST /v2/auth/redeem-license → создаёт пользователя + JWT
- [ ] POST /v2/auth/login → обычный вход по username/password
- [ ] GET /v2/auth/me → профиль работает с Bearer

### Медиа
- [ ] POST /v2/sounds/upload → файл загружается
- [ ] GET /v2/sounds/list → список файлов возвращается
- [ ] URL начинается с https://media.ttboost.pro/static/...
- [ ] Файлы доступны по прямой ссылке (CORS OK)

### Триггеры
- [ ] POST /v2/triggers/set → создание триггера
- [ ] GET /v2/triggers/list → список триггеров
- [ ] POST /v2/triggers/delete → удаление

### WebSocket
- [ ] wss://api.ttboost.pro/v2/ws?token=JWT → подключение OK
- [ ] События TikTok Live приходят (если стрим активен)
- [ ] TTS генерируется и URL абсолютный

### База данных
- [ ] PostgreSQL подключена (DATABASE_URL работает)
- [ ] Таблицы созданы (users, license_keys, triggers, etc.)
- [ ] Связь LicenseKey ↔ User работает

### Безопасность
- [ ] JWT_SECRET задан (уникальный, сложный)
- [ ] ADMIN_API_KEY задан (защита /v2/license/issue)
- [ ] Пароли хешируются pbkdf2_sha256
- [ ] HTTPS работает (certbot/Let's Encrypt)

### Nginx
- [ ] api.ttboost.pro → Uvicorn (порт 8000)
- [ ] media.ttboost.pro → /var/ttboost/media/ (alias)
- [ ] WebSocket upgrade работает (Connection: upgrade)
- [ ] CORS заголовки на media домене

### Systemd
- [ ] Сервис ttboost.service запущен и включён
- [ ] Автозапуск при перезагрузке (enabled)
- [ ] Логи пишутся в /var/log/ttboost/

---

## 🚨 Типичные проблемы и решения

| Проблема | Диагностика | Решение |
|----------|-------------|---------|
| 401 на /v2/ws | `wscat` без токена или неверный токен | Добавить `?token=<JWT>` в URL |
| 500 на /v2/auth/redeem-license | Лицензия не найдена в БД | Сначала выдать через /v2/license/issue |
| TikTok UserNotFoundError в логах | Username не задан или неверный | Проверить что username = TikTok ник (без @) |
| Медиа файлы 404 | Nginx alias неверный | Проверить `location /static/` в media.ttboost.pro |
| WebSocket disconnect сразу | Токен истёк (TTL) | Перелогиниться и получить новый JWT |

---

## 📊 Мониторинг

### Логи
```bash
# Uvicorn
tail -f /var/log/ttboost/uvicorn.out.log
tail -f /var/log/ttboost/uvicorn.err.log

# Nginx
tail -f /var/log/nginx/access.log
tail -f /var/log/nginx/error.log

# Systemd
sudo journalctl -u ttboost -f
```

### Проверка статуса
```bash
sudo systemctl status ttboost
sudo systemctl status nginx
```

### Проверка БД
```bash
psql 'postgresql://ttboost:PASSWORD@localhost:5432/ttboost' -c '\dt'
```

---

## 🔄 Обновление (CI/CD)

```bash
cd /opt/ttboost
sudo -u www-data git pull
source .venv/bin/activate
pip install -r backend/requirements.txt --upgrade
sudo systemctl restart ttboost
sudo systemctl status ttboost
curl -s https://api.ttboost.pro/ | jq
```

---

## 📦 Резервное копирование

### База данных (ежедневно)
```bash
pg_dump ttboost > /backup/ttboost_$(date +%F).sql
```

### Медиа файлы
```bash
rsync -av /var/ttboost/media/ /backup/media/
```

### .env
```bash
cp /opt/ttboost/backend/.env /backup/.env.$(date +%F)
```

---

## 🎯 Следующие шаги

1. **Мобильное приложение**
   - Обновить ApiService для работы с /v2/auth/redeem-license
   - Заменить старый WS на wss://api.ttboost.pro/v2/ws?token=JWT
   - Добавить экран ввода лицензионного ключа

2. **Веб-приложение для покупки**
   - Создать страницу оформления заказа
   - Интеграция с платёжной системой
   - Автовыдача ключа через /v2/license/issue
   - Личный кабинет: просмотр активных лицензий

3. **Аналитика**
   - Добавить логирование событий (Event model)
   - Статистика по стримам (StreamSession)
   - Dashboard админа

4. **Оптимизация**
   - Redis для кеширования TTS
   - CDN для media.ttboost.pro
   - Rate limiting (fastapi-limiter)

---

**Версия:** 2.0  
**Дата деплоя:** 18.11.2025  
**Статус:** ✅ Production Ready
