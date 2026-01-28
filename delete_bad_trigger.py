import requests
import json

token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI3ODQxOGRhYy04N2I4LTRkZTMtOTVlNi1kNDlkMzk2MWZhOGUiLCJpYXQiOjE3NjQ0MjEzMDYsImV4cCI6MTc2NDUwNzcwNn0.sqKEnoqvOA-8FX0vLLERE6c3GksAT-hdd6P16Em4fg0"
base = "https://api.ttboost.pro/v2"

# ID неправильного триггера с gift_id='Rose'
bad_trigger_id = "44785329-78a9-4616-be6d-725dd2509b67"

print(f"🗑️ Удаляю неправильный триггер {bad_trigger_id}...")
delete_resp = requests.post(
    f'{base}/triggers/delete',
    headers={'Authorization': f'Bearer {token}'},
    json={'id': bad_trigger_id}
)

if delete_resp.status_code == 200:
    print(f"✅ Триггер успешно удален!")
else:
    print(f"❌ Ошибка удаления: {delete_resp.status_code}")
    print(delete_resp.text)

# Проверяем результат
print(f"\n📋 Проверяю оставшиеся триггеры...")
r = requests.get(f'{base}/triggers/list', headers={'Authorization': f'Bearer {token}'})
response = r.json()
triggers = response.get('triggers', []) if isinstance(response, dict) else response

print(f"\n📊 Всего триггеров: {len(triggers)}\n")

for t in triggers:
    if t.get('event_type') == 'gift':
        print(f"🎁 Gift триггер:")
        print(f"   ID: {t['id']}")
        print(f"   {t['condition_key']}: '{t['condition_value']}'")
        print(f"   Sound: {t.get('action_params', {}).get('sound_filename')}")
        print()
