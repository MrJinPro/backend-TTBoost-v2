"""
Сервис для подключения к Twitch и чтения чата
"""
import asyncio
from typing import Callable, Optional
from twitchio.ext import commands
import logging

logger = logging.getLogger(__name__)


class TwitchBot(commands.Bot):
    """Бот для чтения чата Twitch"""
    
    def __init__(self, token: str, channel: str, on_message_callback: Callable):
        super().__init__(
            token=token,
            prefix='!',
            initial_channels=[channel]
        )
        self.on_message_callback = on_message_callback
        self.channel_name = channel
        
    async def event_ready(self):
        logger.info(f'Twitch бот подключен к каналу {self.channel_name}')
        
    async def event_message(self, message):
        # Пропускаем сообщения от самого бота
        if message.echo:
            return
            
        # Вызываем callback с данными сообщения
        await self.on_message_callback(
            user=message.author.name,
            text=message.content,
            channel=self.channel_name
        )


class TwitchService:
    """Менеджер для управления Twitch ботами"""
    
    def __init__(self):
        self.bots: dict[str, TwitchBot] = {}
        self.tasks: dict[str, asyncio.Task] = {}
        
    async def start_bot(
        self,
        user_id: str,
        token: str,
        channel: str,
        on_message_callback: Callable
    ):
        """Запустить бота для пользователя"""
        if user_id in self.bots:
            logger.warning(f"Бот для {user_id} уже запущен")
            return
            
        bot = TwitchBot(token, channel, on_message_callback)
        self.bots[user_id] = bot
        
        # Запускаем в фоне
        task = asyncio.create_task(bot.start())
        self.tasks[user_id] = task
        logger.info(f"Twitch бот запущен для пользователя {user_id}, канал {channel}")
        
    async def stop_bot(self, user_id: str):
        """Остановить бота"""
        if user_id not in self.bots:
            return
            
        bot = self.bots[user_id]
        await bot.close()
        
        task = self.tasks.get(user_id)
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
                
        del self.bots[user_id]
        if user_id in self.tasks:
            del self.tasks[user_id]
            
        logger.info(f"Twitch бот остановлен для {user_id}")
        
    def is_running(self, user_id: str) -> bool:
        """Проверить, запущен ли бот"""
        return user_id in self.bots


# Глобальный экземпляр
twitch_service = TwitchService()
