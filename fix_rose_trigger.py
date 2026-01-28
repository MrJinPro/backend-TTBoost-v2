import requests
import json

token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI3ODQxOGRhYy04N2I4LTRkZTMtOTVlNi1kNDlkMzk2MWZhOGUiLCJpYXQiOjE3NjQ0MjEzMDYsImV4cCI6MTc2NDUwNzcwNn0.sqKEnoqvOA-8FX0vLLERE6c3GksAT-hdd6P16Em4fg0"
base = "https://api.ttboost.pro/v2"

# Получаем все триггеры
r = requests.get(f'{base}/triggers/list', headers={'Authorization': f'Bearer {token}'})
response = r.json()
triggers = response.get('triggers', []) if isinstance(response, dict) else response

print(f"\n📊 Найдено триггеров: {len(triggers)}\n")

# Ищем триггер с Rose
rose_trigger = None
for t in triggers:
    if t.get('condition_key') == 'gift_id' and t.get('condition_value') == 'Rose':
        rose_trigger = t
        print(f"❌ Найден НЕПРАВИЛЬНЫЙ триггер:")
        print(f"   ID: {t['id']}")
        print(f"   Event: {t['event_type']}")
        print(f"   Key: {t['condition_key']} (должен быть gift_name)")
        print(f"   Value: '{t['condition_value']}'")
        print(f"\nУдаляю старый триггер...")
        
        # Удаляем старый триггер
        delete_resp = requests.post(
            f'{base}/triggers/delete',
            headers={'Authorization': f'Bearer {token}'},
            json={
                'event_type': t['event_type'],
                'condition_key': t['condition_key'],
                'condition_value': t['condition_value']
            }
        )
        print(f"Удаление: {delete_resp.status_code}")
        
        # Создаем новый с правильным ключом
        print(f"\nСоздаю ПРАВИЛЬНЫЙ триггер с gift_name...")
        create_resp = requests.post(
            f'{base}/triggers/set',
            headers={'Authorization': f'Bearer {token}'},
            json={
                'event_type': 'gift',
                'condition_key': 'gift_name',  # ПРАВИЛЬНЫЙ ключ
                'condition_value': 'Rose',
                'enabled': True,
                'priority': 0,
                'action': 'play_sound',
                'sound_filename': t.get('action_params', {}).get('sound_filename', 'memy.mp3')
            }
        )
        print(f"Создание: {create_resp.status_code}")
        if create_resp.status_code == 200:
            print(f"✅ Триггер исправлен!")
        break

if not rose_trigger:
    print("⚠️ Триггер с Rose не найден")
