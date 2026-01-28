# TTBoost Sign Server

Легкий HTTP-сервис для подписи TikTok Webcast-запросов. Позволяет использовать библиотеку TikTokLive без сторонних лимитов.

## Структура
- `index.js` — HTTP-сервер (POST /sign)
- `tiktok_signer.js` — реализация подписи (можете заменить на свою)
- `package.json` — зависимости и запуск

## Установка и запуск
```powershell
cd sign-server
npm install
npm start
```
Сервер поднимется на `http://localhost:3000` и примет запросы на `POST /sign`.

## Формат запроса
```json
{
  "url": "https://webcast.tiktok.com/webcast/im/fetch/...",
  "userAgent": "Mozilla/5.0 ..."
}
```

## Формат ответа
```json
{
  "signed_url": "https://webcast...&X-Bogus=...",
  "xBogus": "...",
  "userAgent": "Mozilla/5.0 ..."
}
```

## Настройка бэкенда TTBoost
В файле `backend/.env` задайте:
```
SIGN_SERVER_URL=http://localhost:3000/sign
```
Перезапустите бэкенд. Он автоматически попробует использовать Sign Server.

## Важно
- Пример алгоритма в `tiktok_signer.js` — упрощенный и предназначен как заглушка/демонстрация интерфейса.
- Для продакшена замените логику на свою актуальную реализацию.
- Не злоупотребляйте частыми переподключениями — TikTok применяет rate limit.
