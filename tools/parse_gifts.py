#!/usr/bin/env python3
"""
Парсинг tiktok-gifts.js и создание gifts_library.json с русскими названиями
"""
import json
import re
from pathlib import Path

# Словарь переводов для популярных подарков
TRANSLATIONS = {
    "Rose": "Роза",
    "TikTok": "ТикТок",
    "Heart": "Сердце",
    "Panda": "Панда",
    "Lion": "Лев",
    "Finger Heart": "Сердечко пальцами",
    "GG": "GG",
    "Ice Cream Cone": "Мороженое",
    "Rainbow Puke": "Радужная блевотина",
    "Perfume": "Духи",
    "Hand Hearts": "Сердца руками",
    "Thumbs Up": "Большой палец вверх",
    "Sending Love": "Посылаю любовь",
    "Drama Queen": "Драма квин",
    "Confetti": "Конфетти",
    "Love You": "Люблю тебя",
    "Birthday Cake": "Торт",
    "Donuts": "Пончики",
    "Bouquet": "Букет",
    "Doughnut": "Пончик",
    "Swan": "Лебедь",
    "Sunset Speedway": "Закатная трасса",
    "Sports Car": "Спортивная машина",
    "Firecracker": "Петарда",
    "Corgi": "Корги",
    "Galaxy": "Галактика",
    "Cap": "Кепка",
    "Hands": "Руки",
    "Rabbit": "Кролик",
    "Money Gun": "Пистолет денег",
    "Cheer For You": "Болею за тебя",
    "Champion": "Чемпион",
    "Motorcycle": "Мотоцикл",
    "Fly Love": "Летящая любовь",
    "Shuttle": "Шаттл",
    "Yacht": "Яхта",
    "Celebrate": "Праздник",
    "Star": "Звезда",
    "Crown": "Корона",
    "Diamond": "Бриллиант",
    "Castle": "Замок",
    "Rocket": "Ракета",
    "Planet": "Планета",
    "Dragon": "Дракон",
    "Phoenix": "Феникс",
    "Unicorn": "Единорог",
    "Whale": "Кит",
    "Dolphin": "Дельфин",
    "Penguin": "Пингвин",
    "Koala": "Коала",
    "Elephant": "Слон",
    "Tiger": "Тигр",
    "Wolf": "Волк",
    "Bear": "Медведь",
    "Cat": "Кот",
    "Dog": "Собака",
    "Butterfly": "Бабочка",
    "Flower": "Цветок",
    "Sun": "Солнце",
    "Moon": "Луна",
    "Rainbow": "Радуга",
    "Thunder": "Гром",
    "Fire": "Огонь",
    "Ice": "Лёд",
    "Water": "Вода",
    "Earth": "Земля",
    "Wind": "Ветер",
    "Love": "Любовь",
    "Kiss": "Поцелуй",
    "Hug": "Обнимашки",
    "Ring": "Кольцо",
    "Necklace": "Ожерелье",
    "Earrings": "Серьги",
    "Bracelet": "Браслет",
    "Watch": "Часы",
    "Glasses": "Очки",
    "Hat": "Шляпа",
    "Scarf": "Шарф",
    "Gloves": "Перчатки",
    "Shoes": "Туфли",
    "Boots": "Ботинки",
    "Bag": "Сумка",
    "Backpack": "Рюкзак",
    "Umbrella": "Зонт",
    "Camera": "Камера",
    "Phone": "Телефон",
    "Laptop": "Ноутбук",
    "Tablet": "Планшет",
    "Headphones": "Наушники",
    "Microphone": "Микрофон",
    "Guitar": "Гитара",
    "Piano": "Пианино",
    "Drum": "Барабан",
    "Violin": "Скрипка",
    "Saxophone": "Саксофон",
    "Trumpet": "Труба",
    "Flute": "Флейта",
    "Harp": "Арфа",
    "Music": "Музыка",
    "Note": "Нота",
    "Dance": "Танец",
    "Sing": "Пение",
    "Party": "Вечеринка",
    "Beer": "Пиво",
    "Wine": "Вино",
    "Champagne": "Шампанское",
    "Cocktail": "Коктейль",
    "Coffee": "Кофе",
    "Tea": "Чай",
    "Juice": "Сок",
    "Milk": "Молоко",
    "Bread": "Хлеб",
    "Cheese": "Сыр",
    "Pizza": "Пицца",
    "Burger": "Бургер",
    "Fries": "Картофель фри",
    "Hotdog": "Хот-дог",
    "Taco": "Тако",
    "Burrito": "Буррито",
    "Sushi": "Суши",
    "Ramen": "Рамен",
    "Noodles": "Лапша",
    "Rice": "Рис",
    "Egg": "Яйцо",
    "Bacon": "Бекон",
    "Steak": "Стейк",
    "Chicken": "Курица",
    "Fish": "Рыба",
    "Shrimp": "Креветка",
    "Lobster": "Лобстер",
    "Crab": "Краб",
    "Octopus": "Осьминог",
    "Squid": "Кальмар",
    "Apple": "Яблоко",
    "Banana": "Банан",
    "Orange": "Апельсин",
    "Grape": "Виноград",
    "Strawberry": "Клубника",
    "Cherry": "Вишня",
    "Watermelon": "Арбуз",
    "Pineapple": "Ананас",
    "Mango": "Манго",
    "Peach": "Персик",
    "Pear": "Груша",
    "Lemon": "Лимон",
    "Lime": "Лайм",
    "Coconut": "Кокос",
    "Avocado": "Авокадо",
    "Tomato": "Томат",
    "Carrot": "Морковь",
    "Broccoli": "Брокколи",
    "Corn": "Кукуруза",
    "Potato": "Картофель",
    "Onion": "Лук",
    "Garlic": "Чеснок",
    "Pepper": "Перец",
    "Mushroom": "Гриб",
    "Cake": "Торт",
    "Cupcake": "Кекс",
    "Cookie": "Печенье",
    "Candy": "Конфета",
    "Lollipop": "Леденец",
    "Chocolate": "Шоколад",
    "Honey": "Мёд",
    "Jam": "Джем",
    "Butter": "Масло",
    "Salt": "Соль",
    "Sugar": "Сахар",
    "Spice": "Специя"
}

def parse_gifts_js(file_path: Path) -> list:
    """Парсинг tiktok-gifts.js файла"""
    content = file_path.read_text(encoding='utf-8')
    
    # Находим массив TIKTOK_GIFTS
    match = re.search(r'const TIKTOK_GIFTS = (\[[\s\S]*?\]);', content)
    if not match:
        raise ValueError("Не найден массив TIKTOK_GIFTS")
    
    # Парсим JSON
    gifts_json = match.group(1)
    gifts = json.loads(gifts_json)
    
    return gifts

def translate_gift_name(name: str) -> str:
    """Перевод названия подарка на русский"""
    # Прямой перевод
    if name in TRANSLATIONS:
        return TRANSLATIONS[name]
    
    # Попытка частичного перевода
    for en, ru in TRANSLATIONS.items():
        if en.lower() in name.lower():
            return name.replace(en, ru)
    
    # Если нет перевода - оставляем английское
    return name

def create_library(gifts: list) -> list:
    """Создание библиотеки с русскими названиями"""
    library = []
    
    for gift in gifts:
        gift_id = gift.get('id')
        name_en = gift.get('name', '')
        image = gift.get('image', '')
        coins = gift.get('coins', 0)
        
        # Переводим название
        name_ru = translate_gift_name(name_en)
        
        library.append({
            'gift_id': gift_id,
            'name_en': name_en,
            'name_ru': name_ru,
            'image': image,
            'diamond_count': coins
        })
    
    return library

def main():
    # Пути
    root = Path(__file__).parent.parent.parent
    gifts_js = root / 'tiktok-gifts.js'
    output_json = root / 'backend' / 'data' / 'gifts_library.json'
    
    print(f"📖 Парсинг {gifts_js}...")
    gifts = parse_gifts_js(gifts_js)
    print(f"✅ Найдено {len(gifts)} подарков")
    
    print("🌍 Создание библиотеки с переводами...")
    library = create_library(gifts)
    
    # Создаем директорию если нет
    output_json.parent.mkdir(parents=True, exist_ok=True)
    
    # Сохраняем
    output_json.write_text(json.dumps(library, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"💾 Сохранено в {output_json}")
    print(f"📊 Всего подарков: {len(library)}")
    
    # Статистика переводов
    translated = sum(1 for g in library if g['name_ru'] != g['name_en'])
    print(f"🌐 Переведено: {translated}/{len(library)} ({translated/len(library)*100:.1f}%)")

if __name__ == '__main__':
    main()
