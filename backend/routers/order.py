from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from database import supabase
from datetime import datetime

router = APIRouter(prefix="/api")

class OrderCreateRequest(BaseModel):
    customer_id: str
    call_id: str

class OrderAddItemRequest(BaseModel):
    order_id: str
    item_name: str
    quantity: int
    unit_price: float

class OrderUpdateItemRequest(BaseModel):
    order_id: str
    item_name: str
    new_quantity: int

class OrderConfirmRequest(BaseModel):
    order_id: str

class OrderCancelRequest(BaseModel):
    order_id: str

@router.post("/order/create")
def create_order(req: OrderCreateRequest):
    res = supabase.table("orders").insert({
        "customer_id": req.customer_id,
        "call_id": req.call_id,
        "status": "pending",
        "total_amount": 0
    }).execute()
    return res.data[0]

@router.post("/order/add-item")
def add_item(req: OrderAddItemRequest):
    # Triggers handle subtotal automatically. We just insert.
    res = supabase.table("order_items").insert({
        "order_id": req.order_id,
        "item_name": req.item_name,
        "quantity": req.quantity,
        "unit_price": req.unit_price
    }).execute()
    
    # After inserting, return the parent order to show updated total (updated by trigger)
    order_res = supabase.table("orders").select("*").eq("id", req.order_id).execute()
    return order_res.data[0] if order_res.data else None

@router.post("/order/update-item")
def update_item(req: OrderUpdateItemRequest):
    # Find item
    item_res = supabase.table("order_items").select("*").eq("order_id", req.order_id).eq("item_name", req.item_name).execute()
    if not item_res.data:
        raise HTTPException(status_code=404, detail="Item not found")
    
    item = item_res.data[0]
    supabase.table("order_items").update({
        "quantity": req.new_quantity
    }).eq("id", item["id"]).execute()
    
    # Return updated order
    order_res = supabase.table("orders").select("*").eq("id", req.order_id).execute()
    return order_res.data[0] if order_res.data else None

@router.post("/order/confirm")
def confirm_order(req: OrderConfirmRequest):
    order_res = supabase.table("orders").update({
        "status": "confirmed",
        "confirmed_at": datetime.utcnow().isoformat()
    }).eq("id", req.order_id).execute()
    
    if not order_res.data:
        raise HTTPException(status_code=404, detail="Order not found")
        
    order = order_res.data[0]
    
    # Update total_orders on customer
    cust_res = supabase.table("customers").select("total_orders").eq("id", order["customer_id"]).execute()
    if cust_res.data:
        curr_total = cust_res.data[0].get("total_orders") or 0
        supabase.table("customers").update({"total_orders": curr_total + 1}).eq("id", order["customer_id"]).execute()
        
    # Get all items
    items_res = supabase.table("order_items").select("*").eq("order_id", req.order_id).execute()
    order["items"] = items_res.data
    return order

@router.post("/order/cancel")
def cancel_order(req: OrderCancelRequest):
    res = supabase.table("orders").update({
        "status": "cancelled"
    }).eq("id", req.order_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Order not found")
    return res.data[0]

@router.get("/orders")
def get_orders():
    res = supabase.table("orders").select("*, customers(name, phone_number), order_items(*)").order("created_at", desc=True).execute()
    return res.data
