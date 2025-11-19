from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class Gift(BaseModel):
    id: str
    name: str
    image_url: str
    diamond_cost: int | None = None


# Библиотека подарков TikTok
GIFTS = [
    Gift(id="Rose", name="Роза", image_url="https://p16-webcast.tiktokcdn.com/img/maliva/webcast-va/eba3a9bb85c33e017f3648c1b88c4c24~tplv-obj.png", diamond_cost=1),
    Gift(id="TikTok", name="TikTok", image_url="https://p16-webcast.tiktokcdn.com/img/maliva/webcast-va/7c72f1ac6f22b74c18d3e3e6b63df737~tplv-obj.png", diamond_cost=1),
    Gift(id="Finger Heart", name="Палец-сердце", image_url="https://p16-webcast.tiktokcdn.com/img/maliva/webcast-va/3fbae519466d3c7f0c03f30586c2d5c9~tplv-obj.png", diamond_cost=5),
    Gift(id="Heart Me", name="Сердечко", image_url="https://p16-webcast.tiktokcdn.com/img/maliva/webcast-va/3ad7d7ad21b949cf7fd81e0c5b8c1bc7~tplv-obj.png", diamond_cost=10),
    Gift(id="GG", name="GG", image_url="https://p16-webcast.tiktokcdn.com/img/maliva/webcast-va/d123c4e1c6fe4e0eb87f24199469ae2e~tplv-obj.png", diamond_cost=10),
    Gift(id="Ice Cream Cone", name="Мороженое", image_url="https://p16-webcast.tiktokcdn.com/img/maliva/webcast-va/d4f9c7c0e6c1e5f1b4f5c0e7f5c0e7f5~tplv-obj.png", diamond_cost=20),
    Gift(id="Doughnut", name="Пончик", image_url="https://p16-webcast.tiktokcdn.com/img/maliva/webcast-va/b7e8c5f0e6c1e5f1b4f5c0e7f5c0e7f5~tplv-obj.png", diamond_cost=30),
    Gift(id="Perfume", name="Духи", image_url="https://p16-webcast.tiktokcdn.com/img/maliva/webcast-va/e9f1c5f0e6c1e5f1b4f5c0e7f5c0e7f5~tplv-obj.png", diamond_cost=20),
    Gift(id="Sunglasses", name="Очки", image_url="https://p16-webcast.tiktokcdn.com/img/maliva/webcast-va/f2e5c5f0e6c1e5f1b4f5c0e7f5c0e7f5~tplv-obj.png", diamond_cost=50),
    Gift(id="Cap", name="Кепка", image_url="https://p16-webcast.tiktokcdn.com/img/maliva/webcast-va/a3f6c5f0e6c1e5f1b4f5c0e7f5c0e7f5~tplv-obj.png", diamond_cost=50),
    Gift(id="Butterfly", name="Бабочка", image_url="https://p16-webcast.tiktokcdn.com/img/maliva/webcast-va/c4g7c5f0e6c1e5f1b4f5c0e7f5c0e7f5~tplv-obj.png", diamond_cost=88),
    Gift(id="Crown", name="Корона", image_url="https://p16-webcast.tiktokcdn.com/img/maliva/webcast-va/d5h8c5f0e6c1e5f1b4f5c0e7f5c0e7f5~tplv-obj.png", diamond_cost=100),
    Gift(id="Sports Car", name="Спорткар", image_url="https://p16-webcast.tiktokcdn.com/img/maliva/webcast-va/e6i9c5f0e6c1e5f1b4f5c0e7f5c0e7f5~tplv-obj.png", diamond_cost=150),
    Gift(id="Motorcycle", name="Мотоцикл", image_url="https://p16-webcast.tiktokcdn.com/img/maliva/webcast-va/f7j0c5f0e6c1e5f1b4f5c0e7f5c0e7f5~tplv-obj.png", diamond_cost=200),
    Gift(id="Diamond Ring", name="Кольцо с бриллиантом", image_url="https://p16-webcast.tiktokcdn.com/img/maliva/webcast-va/g8k1c5f0e6c1e5f1b4f5c0e7f5c0e7f5~tplv-obj.png", diamond_cost=300),
    Gift(id="Drama Queen", name="Королева драмы", image_url="https://p16-webcast.tiktokcdn.com/img/maliva/webcast-va/h9l2c5f0e6c1e5f1b4f5c0e7f5c0e7f5~tplv-obj.png", diamond_cost=500),
    Gift(id="Swan", name="Лебедь", image_url="https://p16-webcast.tiktokcdn.com/img/maliva/webcast-va/i0m3c5f0e6c1e5f1b4f5c0e7f5c0e7f5~tplv-obj.png", diamond_cost=699),
    Gift(id="Lion", name="Лев", image_url="https://p16-webcast.tiktokcdn.com/img/maliva/webcast-va/j1n4c5f0e6c1e5f1b4f5c0e7f5c0e7f5~tplv-obj.png", diamond_cost=1000),
    Gift(id="Planet", name="Планета", image_url="https://p16-webcast.tiktokcdn.com/img/maliva/webcast-va/k2o5c5f0e6c1e5f1b4f5c0e7f5c0e7f5~tplv-obj.png", diamond_cost=1500),
    Gift(id="Yacht", name="Яхта", image_url="https://p16-webcast.tiktokcdn.com/img/maliva/webcast-va/l3p6c5f0e6c1e5f1b4f5c0e7f5c0e7f5~tplv-obj.png", diamond_cost=2000),
    Gift(id="Fireworks", name="Фейерверк", image_url="https://p16-webcast.tiktokcdn.com/img/maliva/webcast-va/m4q7c5f0e6c1e5f1b4f5c0e7f5c0e7f5~tplv-obj.png", diamond_cost=3000),
    Gift(id="Castle", name="Замок", image_url="https://p16-webcast.tiktokcdn.com/img/maliva/webcast-va/n5r8c5f0e6c1e5f1b4f5c0e7f5c0e7f5~tplv-obj.png", diamond_cost=5000),
    Gift(id="Universe", name="Вселенная", image_url="https://p16-webcast.tiktokcdn.com/img/maliva/webcast-va/o6s9c5f0e6c1e5f1b4f5c0e7f5c0e7f5~tplv-obj.png", diamond_cost=10000),
]


@router.get("/list")
def list_gifts():
    """Получить список всех доступных подарков"""
    return {
        "gifts": [g.model_dump() for g in GIFTS],
        "total": len(GIFTS)
    }


@router.get("/{gift_id}")
def get_gift(gift_id: str):
    """Получить информацию о конкретном подарке"""
    gift = next((g for g in GIFTS if g.id == gift_id), None)
    if not gift:
        return {"error": "Gift not found"}
    return gift.model_dump()
