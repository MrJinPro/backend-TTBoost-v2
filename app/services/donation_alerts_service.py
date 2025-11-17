"""
Сервис для подключения к Donation Alerts
"""
import asyncio
import json
import logging
from typing import Callable, Optional
import websockets
from websockets.client import WebSocketClientProtocol

logger = logging.getLogger(__name__)


class DonationAlertsService:
    """Сервис для получения донатов через Donation Alerts WebSocket"""
    
    def __init__(self):
        self.connections: dict[str, WebSocketClientProtocol] = {}
        self.tasks: dict[str, asyncio.Task] = {}
        
    async def connect(
        self,
        user_id: str,
        token: str,
        on_donation_callback: Callable
    ):
        """Подключиться к Donation Alerts WebSocket"""
        if user_id in self.connections:
            logger.warning(f"Соединение для {user_id} уже существует")
            return
            
        # Centrifugo WebSocket URL для Donation Alerts
        ws_url = f"wss://centrifugo.donationalerts.com/connection/websocket"
        
        task = asyncio.create_task(
            self._listen(user_id, ws_url, token, on_donation_callback)
        )
        self.tasks[user_id] = task
        logger.info(f"Подключение к Donation Alerts для {user_id}")
        
    async def _listen(
        self,
        user_id: str,
        ws_url: str,
        token: str,
        callback: Callable
    ):
        """Слушать события от Donation Alerts"""
        try:
            async with websockets.connect(ws_url) as websocket:
                self.connections[user_id] = websocket
                
                # Отправляем авторизацию
                auth_message = {
                    "params": {
                        "token": token
                    },
                    "id": 1
                }
                await websocket.send(json.dumps(auth_message))
                
                # Слушаем события
                async for message in websocket:
                    data = json.loads(message)
                    
                    # Обрабатываем донаты
                    if "result" in data and "data" in data["result"]:
                        event_data = data["result"]["data"]
                        
                        # Вызываем callback
                        await callback(
                            user=event_data.get("username", "Аноним"),
                            amount=event_data.get("amount", 0),
                            message=event_data.get("message", ""),
                            currency=event_data.get("currency", "RUB")
                        )
                        
        except Exception as e:
            logger.error(f"Ошибка WebSocket для {user_id}: {e}")
        finally:
            if user_id in self.connections:
                del self.connections[user_id]
                
    async def disconnect(self, user_id: str):
        """Отключиться от Donation Alerts"""
        if user_id in self.connections:
            await self.connections[user_id].close()
            del self.connections[user_id]
            
        if user_id in self.tasks:
            self.tasks[user_id].cancel()
            try:
                await self.tasks[user_id]
            except asyncio.CancelledError:
                pass
            del self.tasks[user_id]
            
        logger.info(f"Отключен от Donation Alerts для {user_id}")
        
    def is_connected(self, user_id: str) -> bool:
        return user_id in self.connections


# Глобальный экземпляр
da_service = DonationAlertsService()
