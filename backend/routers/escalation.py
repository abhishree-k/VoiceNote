from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from database import supabase

router = APIRouter(prefix="/api")

class EscalationCreateRequest(BaseModel):
    call_id: str
    customer_id: str
    reason: str

class EscalationResolveRequest(BaseModel):
    escalation_id: str

@router.post("/escalation/create")
def create_escalation(req: EscalationCreateRequest):
    res = supabase.table("escalations").insert({
        "call_id": req.call_id,
        "customer_id": req.customer_id,
        "reason": req.reason,
        "resolved": False
    }).execute()
    
    # Update call status to escalated
    supabase.table("calls").update({"status": "escalated"}).eq("id", req.call_id).execute()
    
    return res.data[0]

@router.post("/escalation/resolve")
def resolve_escalation(req: EscalationResolveRequest):
    res = supabase.table("escalations").update({
        "resolved": True
    }).eq("id", req.escalation_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Escalation not found")
    return res.data[0]

@router.get("/escalations")
def get_escalations():
    res = supabase.table("escalations").select("*, customers(name, phone_number), calls(*)").eq("resolved", False).execute()
    return res.data
