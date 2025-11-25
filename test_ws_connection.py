"""
Тестовый скрипт для проверки WebSocket подключения к TikTok Live
"""
import asyncio
import websockets
import json
import sys

# Замените на ваш реальный JWT токен
JWT_TOKEN = "YOUR_JWT_TOKEN_HERE"

# URL вашего сервера
WS_URL = "wss://api.ttboost.pro/v2/ws"


async def test_connection():
    url = f"{WS_URL}?token={JWT_TOKEN}"
    print(f"🔌 Подключаюсь к {url[:50]}...")
    
    try:
        async with websockets.connect(url) as websocket:
            print("✅ WebSocket подключен!")
            print("⏳ Ожидание событий (Ctrl+C для выхода)...\n")
            
            async for message in websocket:
                try:
                    data = json.loads(message)
                    msg_type = data.get('type', 'unknown')
                    
                    if msg_type == 'status':
                        print(f"📢 STATUS: {data.get('message')}")
                        print(f"   Connected: {data.get('connected')}")
                    elif msg_type == 'error':
                        print(f"❌ ERROR: {data.get('message')}")
                    elif msg_type == 'chat':
                        print(f"💬 CHAT: @{data.get('user')}: {data.get('message')}")
                    elif msg_type == 'gift':
                        print(f"🎁 GIFT: @{data.get('user')} -> {data.get('gift_name')} x{data.get('count', 1)} ({data.get('diamonds', 0)}💎)")
                    elif msg_type == 'like':
                        print(f"❤️ LIKE: @{data.get('user')} +{data.get('count', 1)}")
                    elif msg_type == 'viewer_join':
                        print(f"👋 JOIN: @{data.get('user')}")
                    elif msg_type == 'follow':
                        print(f"➕ FOLLOW: @{data.get('user')}")
                    elif msg_type == 'subscribe':
                        print(f"⭐ SUBSCRIBE: @{data.get('user')}")
                    elif msg_type == 'share':
                        print(f"📤 SHARE: @{data.get('user')}")
                    elif msg_type == 'viewer':
                        print(f"👥 VIEWERS: current={data.get('current')}, total={data.get('total')}")
                    else:
                        print(f"📦 {msg_type.upper()}: {data}")
                    
                    print()  # пустая строка для читаемости
                    
                except json.JSONDecodeError:
                    print(f"⚠️ Не-JSON сообщение: {message}")
                    
    except websockets.exceptions.InvalidStatusCode as e:
        print(f"❌ Ошибка HTTP: {e.status_code}")
        if e.status_code == 403:
            print("💡 Проверьте JWT токен")
        elif e.status_code == 404:
            print("💡 Endpoint /v2/ws не найден - возможно на сервере старая версия кода")
    except websockets.exceptions.WebSocketException as e:
        print(f"❌ WebSocket ошибка: {e}")
    except KeyboardInterrupt:
        print("\n👋 Отключение...")
    except Exception as e:
        print(f"❌ Неожиданная ошибка: {type(e).__name__}: {e}")


if __name__ == "__main__":
    if JWT_TOKEN == "YOUR_JWT_TOKEN_HERE":
        print("❌ ОШИБКА: Укажите ваш JWT токен в переменной JWT_TOKEN")
        print("\nКак получить токен:")
        print("1. Откройте приложение в браузере")
        print("2. Откройте DevTools (F12) -> Console")
        print("3. Выполните: localStorage.getItem('jwtToken')")
        print("4. Скопируйте токен и вставьте в этот скрипт")
        sys.exit(1)
    
    print("=" * 60)
    print("🧪 Тест WebSocket подключения к TikTok Live")
    print("=" * 60)
    print()
    
    asyncio.run(test_connection())
