from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from database import supabase
from datetime import datetime
import json

router = APIRouter(prefix="/api")

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

@router.post("/call/start")
def start_call(req: CallStartRequest):
    res = supabase.table("calls").insert({
        "customer_id": req.customer_id,
        "twilio_call_sid": req.twilio_call_sid,
        "status": "active",
        "transcript": []
    }).execute()
    return res.data[0]

@router.post("/call/update-transcript")
def update_transcript(req: UpdateTranscriptRequest):
    # Fetch existing
    call_res = supabase.table("calls").select("transcript").eq("id", req.call_id).execute()
    if not call_res.data:
        raise HTTPException(status_code=404, detail="Call not found")
    
    transcript = call_res.data[0].get("transcript") or []
    transcript.append(req.entry.model_dump())
    
    # Update
    res = supabase.table("calls").update({"transcript": transcript}).eq("id", req.call_id).execute()
    return res.data[0]

@router.post("/call/end")
def end_call(req: CallEndRequest):
    res = supabase.table("calls").update({
        "status": req.final_status,
        "language_used": req.language_used,
        "ended_at": datetime.utcnow().isoformat()
    }).eq("id", req.call_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Call not found")
        
    # Also update customer's preferred language
    call = res.data[0]
    supabase.table("customers").update({"preferred_lang": req.language_used}).eq("id", call["customer_id"]).execute()
    
    return call

@router.get("/calls")
def get_calls():
    res = supabase.table("calls").select("*, customers(name, phone_number)").order("started_at", desc=True).limit(10).execute()
    return res.data

@router.get("/call/{call_id}")
def get_call(call_id: str):
    res = supabase.table("calls").select("*").eq("id", call_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Call not found")
    call = res.data[0]
    
    # Get associated order
    order_res = supabase.table("orders").select("*, order_items(*)").eq("call_id", call_id).execute()
    call["order"] = order_res.data[0] if order_res.data else None
    
    return call
