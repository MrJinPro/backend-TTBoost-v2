from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
import os, json

router = APIRouter()

CATALOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', 'catalog')
GIFTS_JSON = os.path.join(CATALOG_DIR, 'gifts.json')


@router.get('/gifts')
async def get_gifts_catalog():
    if not os.path.exists(GIFTS_JSON):
        raise HTTPException(status_code=404, detail='gifts.json not found. Place it under static/catalog/gifts.json')
    try:
        with open(GIFTS_JSON, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return JSONResponse(content={"gifts": data})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'Failed to read gifts catalog: {e}')
