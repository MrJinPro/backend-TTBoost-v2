import requests
import json

token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI3ODQxOGRhYy04N2I4LTRkZTMtOTVlNi1kNDlkMzk2MWZhOGUiLCJpYXQiOjE3NjQ0MjEzMDYsImV4cCI6MTc2NDUwNzcwNn0.sqKEnoqvOA-8FX0vLLERE6c3GksAT-hdd6P16Em4fg0"

r = requests.get('https://api.ttboost.pro/v2/triggers/list', headers={'Authorization': f'Bearer {token}'})
response = r.json()

# Проверяем формат ответа
if isinstance(response, dict) and 'triggers' in response:
    triggers = response['triggers']
elif isinstance(response, list):
    triggers = response
else:
    print(f"⚠️ Неожиданный формат ответа: {response}")
    triggers = []

print(f"\n📊 Всего триггеров: {len(triggers)}\n")

for t in triggers:
    print(f"🔹 ID: {t.get('id', 'N/A')}")
    print(f"   Event: {t.get('event_type', 'N/A')}")
    print(f"   Key: {t.get('condition_key', 'N/A')}")
    print(f"   Value: '{t.get('condition_value', 'N/A')}'")
    print(f"   Enabled: {t.get('enabled', False)}")
    print(f"   Action: {t.get('action', 'N/A')}")
    print(f"   Name: {t.get('trigger_name', 'N/A')}")
    print(f"   Sound: {t.get('action_params', {}).get('sound_filename', 'N/A')}")
    print()
