from fastapi import APIRouter, Request, BackgroundTasks, HTTPException
from fastapi.responses import HTMLResponse
from twilio.twiml.voice_response import VoiceResponse, Connect
from twilio.rest import Client
import logging
import datetime
from config import TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER, NGROK_URL, supabase
from services.session import session_store

router = APIRouter()
logger = logging.getLogger(__name__)

twilio_client = None
if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
    twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

@router.post("/incoming-call")
async def handle_incoming_call(request: Request):
    """
    Twilio Voice webhook receiver. Returns TwiML to open a WebSocket stream.
    """
    form_data = await request.form()
    call_sid = form_data.get("CallSid")
    phone_number = form_data.get("From")
    
    logger.info(f"Incoming call from {phone_number}, CallSid: {call_sid}")
    
    # 1. Supabase Write: On call connect -> INSERT row into calls table
    if supabase:
        try:
            supabase.table("calls").insert({
                "call_sid": call_sid,
                "phone_number": phone_number,
                "status": "in-progress",
                "timestamp": datetime.datetime.utcnow().isoformat()
            }).execute()
        except Exception as e:
            logger.error(f"Supabase insert error on connect: {e}")
            
    # 2. Session Management: Create CallSession
    session = session_store.create_session(call_sid, phone_number)
    
    # 3. Lookup returning customer
    if supabase:
        try:
            res = supabase.table("customers").select("name, last_order").eq("phone_number", phone_number).execute()
            if res.data and len(res.data) > 0:
                customer = res.data[0]
                session.is_returning_customer = True
                session.customer_name = customer.get("name")
                session.last_order = customer.get("last_order")
                session_store.update_session(call_sid, session)
        except Exception as e:
            logger.error(f"Supabase customer lookup error: {e}")

    # 4. Generate TwiML response
    response = VoiceResponse()
    connect = Connect()
    
    stream_url = NGROK_URL.replace("https://", "wss://").replace("http://", "ws://") + "/stream"
    connect.stream(url=stream_url)
    response.append(connect)
    
    return HTMLResponse(content=str(response), media_type="text/xml")

@router.post("/call-status")
async def call_status_callback(request: Request):
    """
    Call status callback handler - receives Twilio's in-progress, completed, failed, no-answer events.
    Writes them to Supabase.
    """
    form_data = await request.form()
    call_sid = form_data.get("CallSid")
    call_status = form_data.get("CallStatus")
    call_duration = form_data.get("CallDuration")
    
    logger.info(f"Call {call_sid} status updated to {call_status}")
    
    session = session_store.get_session(call_sid)
    escalation_flag = session.escalation_flag if session else False
    
    # Supabase Write: On call end -> UPDATE calls row
    if supabase:
        try:
            update_data = {"status": call_status}
            if call_duration:
                update_data["duration"] = int(call_duration)
            if call_status in ["completed", "failed", "busy", "no-answer", "canceled"]:
                update_data["escalation_flag"] = escalation_flag
                
            supabase.table("calls").update(update_data).eq("call_sid", call_sid).execute()
        except Exception as e:
            logger.error(f"Supabase update error on status: {e}")
            
    # Clean up session if call has ended
    if call_status in ["completed", "failed", "busy", "no-answer", "canceled"]:
        session_store.end_session(call_sid)

    return {"status": "received"}

@router.post("/outbound-call")
async def trigger_outbound_call(phone_number: str, customer_metadata: dict = {}):
    """
    Outbound call trigger endpoint - fires a Twilio call programmatically.
    """
    if not twilio_client:
        raise HTTPException(status_code=500, detail="Twilio client not configured.")
        
    http_ngrok = NGROK_URL.replace("wss://", "https://").replace("ws://", "http://")
    
    try:
        call = twilio_client.calls.create(
            to=phone_number,
            from_=TWILIO_PHONE_NUMBER,
            url=f"{http_ngrok}/incoming-call",
            status_callback=f"{http_ngrok}/call-status",
            status_callback_event=["initiated", "ringing", "answered", "completed"],
            status_callback_method="POST"
        )
        return {"call_sid": call.sid, "status": "initiated"}
    except Exception as e:
        logger.error(f"Error triggering outbound call: {e}")
        raise HTTPException(status_code=500, detail=str(e))

def hangup_call(call_sid: str):
    """
    Graceful call termination - utility that hangs up via Twilio REST API.
    """
    if not twilio_client:
        return False
    try:
        twilio_client.calls(call_sid).update(status="completed")
        logger.info(f"Hung up call {call_sid} gracefully.")
        return True
    except Exception as e:
        logger.error(f"Error hanging up call {call_sid}: {e}")
        return False
