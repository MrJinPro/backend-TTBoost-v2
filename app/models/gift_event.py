from pydantic import BaseModel


class GiftEvent(BaseModel):
    type: str = "gift"
    gift_name: str
    count: int
    sound_url: str
