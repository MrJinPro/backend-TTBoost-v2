from pydantic import BaseModel


class ChatEvent(BaseModel):
    type: str = "chat"
    user: str
    message: str
    tts_url: str
