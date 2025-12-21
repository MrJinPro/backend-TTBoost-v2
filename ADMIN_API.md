# Admin API (v2)

## Роли

Роль хранится в `users.role` (строка):

- `user` (обычный пользователь, default)
- `support`
- `curator`
- `moderator`
- `admin`
- `manager` (alias input: `menager`)
- `superadmin`

## Bootstrap SuperAdmin

Чтобы автоматически назначить SuperAdmin указанным аккаунтам, задайте env:

- `SUPERADMIN_USERNAMES` — логины через запятую, например: `SUPERADMIN_USERNAMES=novaboost,owner`

После первого запроса с валидным JWT от такого пользователя его `role` будет установлен в `superadmin`.

## Endpoints

Все эндпоинты требуют `Authorization: Bearer <JWT>`.

- `GET /v2/admin/roles` — список ролей (доступ: staff, т.е. роль выше `user`)
- `GET /v2/admin/users?q=&limit=&offset=` — список пользователей (доступ: staff)
- `PATCH /v2/admin/users/{user_id}/role` — назначить роль (доступ: `superadmin`)
- `PATCH /v2/admin/users/by-username/{username}/role` — назначить роль по username (доступ: `superadmin`)

Body для назначения роли:

```json
{ "role": "support" }
```

Примечания:
- Нельзя понизить самого себя с `superadmin` (защита от случайной потери доступа).
