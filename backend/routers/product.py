from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from database import supabase

router = APIRouter(prefix="/api")

class ProductCreateRequest(BaseModel):
    name: str
    price: float
    sku: str

class ProductUpdateRequest(BaseModel):
    name: Optional[str] = None
    price: Optional[float] = None
    is_available: Optional[bool] = None

@router.get("/products")
def get_products():
    res = supabase.table("products").select("*").eq("is_available", True).execute()
    return res.data

@router.post("/products")
def create_product(req: ProductCreateRequest):
    res = supabase.table("products").insert({
        "name": req.name,
        "price": req.price,
        "sku": req.sku,
        "is_available": True
    }).execute()
    return res.data[0]

@router.patch("/product/{product_id}")
def update_product(product_id: str, req: ProductUpdateRequest):
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
        
    res = supabase.table("products").update(updates).eq("id", product_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Product not found")
    return res.data[0]
