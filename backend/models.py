from pydantic import BaseModel
from typing import Optional, List, Dict, Any

class CustomerLookupRequest(BaseModel):
    phone_number: str

class CallStartRequest(BaseModel):
    customer_id: str
    twilio_call_sid: str

class TranscriptEntry(BaseModel):
    role: str
    message: str

class UpdateTranscriptRequest(BaseModel):
    call_id: str
    entry: TranscriptEntry

class CallEndRequest(BaseModel):
    call_id: str
    final_status: str
    language_used: str

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

class EscalationCreateRequest(BaseModel):
    call_id: str
    customer_id: str
    reason: str

class EscalationResolveRequest(BaseModel):
    escalation_id: str

class ProductCreateRequest(BaseModel):
    name: str
    price: float
    sku: str

class ProductUpdateRequest(BaseModel):
    name: Optional[str] = None
    price: Optional[float] = None
    is_available: Optional[bool] = None
