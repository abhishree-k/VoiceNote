import re
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from database import supabase

router = APIRouter(prefix="/api")

class LookupRequest(BaseModel):
    phone_number: str

def normalize_phone(phone: str) -> str:
    cleaned = re.sub(r'[^\d+]', '', phone)
    if not cleaned.startswith('+'):
        # prepend + to assume E.164
        cleaned = '+' + cleaned
    return cleaned

@router.post("/customer/lookup")
def lookup_customer(req: LookupRequest):
    phone = normalize_phone(req.phone_number)
    res = supabase.table("customers").select("*").eq("phone_number", phone).execute()
    data = res.data
    
    if len(data) == 0:
        # Create new
        new_cust = supabase.table("customers").insert({"phone_number": phone}).execute()
        created = new_cust.data[0]
        created["is_new_customer"] = True
        return created
    else:
        customer = data[0]
        customer["is_new_customer"] = False
        
        # Get last 3 orders with items
        orders_res = supabase.table("orders").select("*, order_items(*)").eq("customer_id", customer["id"]).order("created_at", desc=True).limit(3).execute()
        customer["last_orders"] = orders_res.data
        return customer

@router.get("/customers")
def get_customers():
    res = supabase.table("customers").select("*").execute()
    return res.data

@router.get("/customer/{customer_id}")
def get_customer(customer_id: str):
    cust_res = supabase.table("customers").select("*").eq("id", customer_id).execute()
    if not cust_res.data:
        raise HTTPException(status_code=404, detail="Customer not found")
        
    customer = cust_res.data[0]
    orders_res = supabase.table("orders").select("*, order_items(*)").eq("customer_id", customer_id).order("created_at", desc=True).execute()
    customer["orders"] = orders_res.data
    return customer
