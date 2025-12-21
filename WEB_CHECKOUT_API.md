# ТЗ для Lovable: веб‑оплата → выдача ключа → активация тарифа

Цель: сделать веб‑страницу покупки тарифа. После подтверждения оплаты веб выдаёт пользователю лицензионный ключ. Пользователь вводит этот ключ в приложении (Profile) и тариф активируется.

Важно: на вебе используется та же авторизация, что и в приложении (JWT от backend через `/v2/auth/*`).

## 0) Конфигурация (что Lovable должен уметь настраивать)

### Backend base URL

- `BACKEND_BASE_URL` — например `https://api.ttboost.pro` или `http://localhost:8000`

Все запросы ниже идут в `${BACKEND_BASE_URL}`.

### CORS (важно для browser fetch)

Чтобы браузерный `fetch()` к `${BACKEND_BASE_URL}` работал, backend должен разрешать origin вашего сайта.

- На backend есть переменная окружения `ALLOWED_ORIGINS` (через запятую), например:
  - `ALLOWED_ORIGINS=https://ttboost.pro,https://www.ttboost.pro,https://mobile.ttboost.pro`

Важно:
- В `ALLOWED_ORIGINS` нужно указывать именно **origin** (scheme + host + port). Путь (`/profile`) в `Origin` не входит.
  - Пример: если страница `https://novaboost.lovable.app/profile`, то `Origin` будет `https://novaboost.lovable.app`.
- Допускается и формат без схемы (только хост): `novaboost.lovable.app`, но предпочтительнее явный `https://...`.

Если CORS не настроен, в DevTools часто видно `401`/`200` в Network, но в Console будет ошибка вида «Не удалось загрузить Fetch» — это блокировка CORS.

### Секреты (только server-side)

- `WEB_ISSUE_API_KEY` — секрет для `POST /v2/license/issue-web`.
- Ключи платёжного провайдера (как минимум secret для webhook verification) — зависят от провайдера.

Нельзя: хранить `WEB_ISSUE_API_KEY` в браузере.

### Ограничение продаваемых планов (на backend)

- `WEB_ALLOWED_PLANS` (опционально) — ids планов через запятую, например: `nova_streamer_one_mobile,nova_streamer_duo`

## 1) Авторизация на вебе (как в приложении)

Веб‑клиент должен работать с JWT:

- после логина/регистрации хранить `access_token` (например, в `localStorage`)
- добавлять заголовок `Authorization: Bearer <access_token>` для защищённых запросов

### Регистрация

`POST ${BACKEND_BASE_URL}/v2/auth/register`

Body:
```json
{ "username": "my_login", "password": "my_password" }
```

Response:
```json
{ "access_token": "...", "token_type": "bearer" }
```

### Логин

`POST ${BACKEND_BASE_URL}/v2/auth/login`

Body:
```json
{ "username": "my_login", "password": "my_password" }
```

Response:
```json
{ "access_token": "...", "token_type": "bearer" }
```

### Получить текущий тариф/срок (для UI)

`GET ${BACKEND_BASE_URL}/v2/auth/me`

Headers:
- `Authorization: Bearer <JWT>`

Response (пример):
```json
{
  "id": "...",
  "username": "...",
  "plan": "nova_streamer_one_mobile",
  "tariff_name": "NovaStreamer One (Mobile)",
  "allowed_platforms": ["mobile"],
  "license_expires_at": "2026-01-20T12:34:56.789Z"
}
```

## 2) API backend для витрины и выдачи ключей

### 2.1 Список тарифов для витрины

`GET ${BACKEND_BASE_URL}/v2/license/plans`

Response:
```json
{
  "items": [
    {"id":"nova_streamer_one_mobile","name":"NovaStreamer One (Mobile)","allowed_platforms":["mobile"]},
    {"id":"nova_streamer_one_desktop","name":"NovaStreamer One (Desktop)","allowed_platforms":["desktop"]},
    {"id":"nova_streamer_duo","name":"NovaStreamer Duo","allowed_platforms":["desktop","mobile"]}
  ]
}
```

### 2.2 Выдать ключ после подтверждения оплаты (ТОЛЬКО server-side)

Этот вызов делает не браузер, а serverless/API route Lovable.

`POST ${BACKEND_BASE_URL}/v2/license/issue-web`

Headers:
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

Response:
```json
{
  "key": "TTB-AAAA-BBBB-CCCC",
  "plan": "nova_streamer_one_mobile",
  "expires_at": "2026-01-20T12:34:56.789Z"
}
```

Гарантии backend:
- идемпотентность по `order_id` (повтор вернёт тот же ключ)
- если задан `WEB_ALLOWED_PLANS`, выдаются только планы из списка

## 3) Что должен сделать Lovable (архитектура веба)

На вебе два слоя:

1) Browser UI (страницы, формы)
2) Server-side (API routes / serverless) — для оплаты и вызова `issue-web`

### 3.1 UI (browser)

Экран/поток:

1) (Опционально) Login/Register — через `/v2/auth/login` и `/v2/auth/register`
2) Загрузка тарифов — `GET /v2/license/plans`
3) Выбор тарифа и оплата — UI вызывает server-side endpoint Lovable `POST /api/checkout/create`
4) После оплаты UI показывает результат:
   - ключ (если получен)
   - срок действия
   - инструкцию по активации в приложении

Важно: UI не должен знать `WEB_ISSUE_API_KEY`.

### 3.2 Server-side (Lovable API routes)

Нужно реализовать минимум 2 server-side endpoint’а:

1) `POST /api/checkout/create`
   - вход: выбранный `plan`, `ttl_days`, `email` (если собираем)
   - действие: создать платёж у провайдера
   - выход: `payment_url` или данные для оплаты

2) `POST /api/checkout/webhook` (URL для webhook от провайдера)
   - действие: проверить подпись webhook
   - если платёж подтверждён: вызвать backend `POST /v2/license/issue-web` и получить ключ
   - сохранить ключ для этого заказа (в БД Lovable) и/или отправить email пользователю
   - вернуть 200 OK провайдеру

Опционально (очень желательно):

3) `GET /api/checkout/status?order_id=...`
   - UI опрашивает статус заказа и получает `license_key` после webhook

## 4) База данных веба (Lovable DB): что хранить и как писать

Зачем нужна БД веба:

- браузер должен получить ключ после webhook (webhook приходит server-to-server)
- нельзя отдавать ключи и данные платежа только через «память»

### 4.1 Таблица заказов (минимальная)

Создать таблицу `web_orders` со столбцами:

- `order_id` (text, unique) — ваш id заказа (будет же `order_id` в `issue-web`)
- `status` (text) — `created` | `paid` | `failed`
- `plan` (text)
- `ttl_days` (int)
- `email` (text, null)
- `amount` (int, null)
- `currency` (text, null)
- `provider` (text, null) — например `yookassa/stripe/...`
- `provider_payment_id` (text, null)
- `license_key` (text, null)
- `license_expires_at` (timestamptz, null)
- `created_at` (timestamptz)
- `updated_at` (timestamptz)

Если Lovable просит SQL (Postgres):
```sql
create table if not exists web_orders (
  order_id text primary key,
  status text not null default 'created',
  plan text not null,
  ttl_days int not null,
  email text null,
  amount int null,
  currency text null,
  provider text null,
  provider_payment_id text null,
  license_key text null,
  license_expires_at timestamptz null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
```

### 4.2 Логика записи в БД (строго)

- `POST /api/checkout/create`:
  - создать `order_id`
  - вставить строку в `web_orders` со `status='created'`, выбранным `plan/ttl_days/email/amount/currency`
  - создать платёж у провайдера и сохранить `provider_payment_id`

- `POST /api/checkout/webhook` (после подтверждения оплаты):
  - найти `web_orders` по `order_id`/`provider_payment_id`
  - если уже есть `license_key` — ничего не делать (идемпотентность)
  - вызвать backend `POST /v2/license/issue-web` (с `Web-Api-Key`)
  - сохранить `license_key` и `license_expires_at`, поставить `status='paid'`

### 4.3 Авторизация для чтения статуса заказа

Так как на вебе «та же авторизация, что в приложении», то доступ к `GET /api/checkout/status` делаем так:

- браузер отправляет `Authorization: Bearer <JWT>`
- server-side endpoint проверяет JWT, вызывая backend `GET /v2/auth/me`
- только после успешной проверки отдаём статус заказа

Примечание: если вы не хотите связывать заказ с пользователем, можно разрешать статус по `order_id`+`email` (но это слабее). Самый простой безопасный вариант — требовать JWT.

## 5) Как активировать ключ (в приложении)

## 5A) Как активировать ключ прямо на вебе (после оплаты)

Веб может активировать ключ сразу (без копипаста в приложение), **если пользователь залогинен** (есть JWT).

`POST ${BACKEND_BASE_URL}/v2/auth/upgrade-license`

Headers:
- `Authorization: Bearer <JWT>`

Body:
```json
{ "license_key": "TTB-AAAA-BBBB-CCCC" }
```

Response:
```json
{
  "status": "ok",
  "plan": "nova_streamer_one_mobile",
  "license_expires_at": "2026-01-20T12:34:56.789Z"
}
```

Примечания:
- Если получаете `404 Not Found` — на сервере задеплоена старая версия backend без этого endpoint’а (нужно обновить деплой).
- На некоторых старых клиентах/деплоях может встречаться алиас `POST /v2/auth/upgrade_license`.

### Рекомендуемый вариант: апгрейд в профиле (пользователь уже вошёл)

`POST ${BACKEND_BASE_URL}/v2/auth/upgrade-license`

Headers:
- `Authorization: Bearer <JWT>`

Body:
```json
{ "license_key": "TTB-AAAA-BBBB-CCCC" }
```

### Альтернатива: регистрация/вход через ключ (если аккаунта нет)

`POST ${BACKEND_BASE_URL}/v2/auth/redeem-license`

Body:
```json
{ "license_key": "TTB-AAAA-BBBB-CCCC", "username": "my_login", "password": "my_password" }
```

## 6) Текст, который показывать пользователю после оплаты (копипаст)

1) Скопируйте ключ: `TTB-....`
2) Откройте приложение TTBoost
3) Перейдите: **Profile → License**
4) Вставьте ключ и нажмите **Activate**

Если ключ потеряется — он также отправлен на email (если email собирался).
