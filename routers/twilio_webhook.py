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

import httpx

@router.post("/incoming-call")
async def handle_incoming_call(request: Request):
    """
    Twilio Voice webhook receiver. Returns TwiML to open a WebSocket stream.
    """
    form_data = await request.form()
    call_sid = form_data.get("CallSid")
    phone_number = form_data.get("From")
    
    logger.info(f"Incoming call from {phone_number}, CallSid: {call_sid}")
    
    # 1. Session Management: Create CallSession
    session = session_store.create_session(call_sid, phone_number)
    
    # 2. Call Backend API: Lookup Customer and Start Call
    try:
        async with httpx.AsyncClient() as client:
            # Lookup customer
            cust_res = await client.post("http://localhost:8001/api/customer/lookup", json={"phone_number": phone_number})
            cust_res.raise_for_status()
            customer = cust_res.json()
            
            session.customer_id = customer.get("id")
            if not customer.get("is_new_customer"):
                session.is_returning_customer = True
                session.customer_name = customer.get("name")
                if customer.get("last_orders"):
                    session.last_order = customer["last_orders"][0] # Store full object for agent
                    
            # Start call in Backend
            call_res = await client.post("http://localhost:8001/api/call/start", json={
                "customer_id": session.customer_id,
                "twilio_call_sid": call_sid
            })
            call_res.raise_for_status()
            call_data = call_res.json()
            session.call_id = call_data.get("id")
            
            # Fetch products for the agent
            prod_res = await client.get("http://localhost:8001/api/products")
            products = prod_res.json() if prod_res.is_success else []

            # Initialize Agent Service
            agent_res = await client.post("http://localhost:4000/agent/start-call", json={
                "callSid": call_sid,
                "callId": session.call_id,
                "customerId": session.customer_id,
                "customerData": {
                    "customer": customer,
                    "lastOrder": session.last_order
                },
                "language": session.language or "english",
                "products": products
            })
            if agent_res.is_success:
                agent_data = agent_res.json()
                # Store the initial greeting to be played when stream starts
                session.order_buffer.append(agent_data.get("reply"))
                logger.info(f"Agent initialized for call {call_sid}")
            
            session_store.update_session(call_sid, session)
    except Exception as e:
        logger.error(f"Error calling backend or agent API on connect: {e}")

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
    Writes them to Supabase via Backend API.
    """
    form_data = await request.form()
    call_sid = form_data.get("CallSid")
    call_status = form_data.get("CallStatus")
    
    logger.info(f"Call {call_sid} status updated to {call_status}")
    
    session = session_store.get_session(call_sid)
    
    if call_status in ["completed", "failed", "busy", "no-answer", "canceled"]:
        if session:
            try:
                async with httpx.AsyncClient() as client:
                    # End call in Agent Service
                    await client.post("http://localhost:4000/agent/end-call", json={"callSid": call_sid})
                    
                    # End call in Backend
                    if session.call_id:
                        await client.post("http://localhost:8001/api/call/end", json={
                            "call_id": session.call_id,
                            "final_status": call_status,
                            "language_used": session.language or "en-IN"
                        })
            except Exception as e:
                logger.error(f"Error calling backend or agent API on call end: {e}")
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
