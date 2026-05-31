from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Optional

router = APIRouter(prefix="/inventory", tags=["Inventory"])

class ItemBase(BaseModel):
    name: str
    quantity: int
    price: float
    description: Optional[str] = None

class ItemCreate(ItemBase):
    pass

class Item(ItemBase):
    id: int

fake_db_items = []

@router.get("/", response_model=List[Item])
async def get_inventory():
    return fake_db_items

@router.post("/", response_model=Item)
async def create_item(item: ItemCreate):
    new_id = len(fake_db_items) + 1
    new_item = Item(id=new_id, **item.model_dump())
    fake_db_items.append(new_item)
    return new_item