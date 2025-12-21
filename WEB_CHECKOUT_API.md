# Веб-оплата → выдача ключа → активация в приложении

Этот документ описывает минимальный «красивый» поток:

1) Пользователь выбирает тариф на веб‑странице.
2) Оплачивает.
3) Получает ключ.
4) В приложении открывает **Profile** → вводит ключ → тариф активируется.

## Важно про безопасность

- `Web-Api-Key` — это **секрет сервера**, его нельзя отдавать в браузер.
- Поэтому нужен **веб‑бэкенд** (или serverless функция), которая:
  - создаёт платёж у провайдера,
  - принимает webhook/подтверждение оплаты,
  - после подтверждения вызывает API backend и получает ключ.

## Тарифы (для витрины)

### `GET /v2/license/plans`
Возвращает список платных тарифов для веб‑витрины.

Ответ:
```json
{
  "items": [
    {"id":"nova_streamer_one_mobile","name":"NovaStreamer One (Mobile)","allowed_platforms":["mobile"]},
    {"id":"nova_streamer_one_desktop","name":"NovaStreamer One (Desktop)","allowed_platforms":["desktop"]},
    {"id":"nova_streamer_duo","name":"NovaStreamer Duo","allowed_platforms":["desktop","mobile"]}
  ]
}
```

Опционально можно ограничить список через env `WEB_ALLOWED_PLANS`.

## Выдача ключа после оплаты (для веб‑бэкенда)

### `POST /v2/license/issue-web`
Header:
- `Web-Api-Key: <WEB_ISSUE_API_KEY>`

Body:
```json
{
  "order_id": "order_12345",
  "plan": "nova_streamer_one_mobile",
  "ttl_days": 30,
  "email": "user@example.com",
  "amount": 9900,
  "currency": "RUB"
}
```

Ответ:
```json
{
  "key": "TTB-AAAA-BBBB-CCCC",
  "plan": "nova_streamer_one_mobile",
  "expires_at": "2026-01-20T12:34:56.789Z"
}
```

Гарантии:
- **Идемпотентность** по `order_id`: повторный вызов вернёт **тот же** ключ.
- Если указан `WEB_ALLOWED_PLANS`, то выдаются только планы из списка.

## Активация ключа в приложении

Есть два варианта.

### Вариант A (рекомендуемый для уже вошедшего пользователя): апгрейд в профиле

1) Пользователь логинится (или уже залогинен).
2) В **Profile** вводит ключ.
3) Приложение вызывает:

#### `POST /v2/auth/upgrade-license`
Header:
- `Authorization: Bearer <JWT>`

Body:
```json
{ "license_key": "TTB-AAAA-BBBB-CCCC" }
```

Ответ:
```json
{ "plan": "nova_streamer_one_mobile", "license_expires_at": "..." }
```

Чтобы обновить UI плана/срока после апгрейда:

#### `GET /v2/auth/me`
Header:
- `Authorization: Bearer <JWT>`

Ответ содержит текущий тариф (`plan`, `tariff_name`, `allowed_platforms`) и `license_expires_at`.

### Вариант B (если аккаунта ещё нет): регистрация/вход через ключ

#### `POST /v2/auth/redeem-license`
Body:
```json
{
  "license_key": "TTB-AAAA-BBBB-CCCC",
  "username": "your_login",
  "password": "your_password"
}
```

Ответ:
```json
{ "access_token": "...", "license_expires_at": "...", "plan": "..." }
```

## Проверка ключа (опционально)

В backend есть:

- `GET /v2/license/check?key=TTB-...`

Это удобно для диагностики, но для веб‑витрины обычно не нужно.

## Переменные окружения

- `WEB_ISSUE_API_KEY` — секрет для `POST /v2/license/issue-web`.
- `WEB_ALLOWED_PLANS` (опционально) — планы через запятую, например:
  - `nova_streamer_one_mobile,nova_streamer_duo`

## Мини‑рекомендация по «красивому» UX

- После оплаты показывайте:
  - ключ,
  - срок (если есть),
  - короткую инструкцию: «Откройте приложение → Profile → поле “Лицензия” → вставьте ключ → нажмите Активировать».
- Дублируйте ключ письмом на `email` (если собираете email).
