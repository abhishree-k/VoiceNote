from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import json
import base64
import logging
import asyncio
from config import CONFIDENCE_THRESHOLD, supabase
from services.session import session_store
from services.stt import recognize_speech
from services.tts import generate_speech
from services.language import determine_language
from routers.twilio_webhook import hangup_call

router = APIRouter()
logger = logging.getLogger(__name__)

async def process_utterance(call_sid: str, transcript: str, language: str) -> str:
    """
    Interface contract with Person 2 (Order Intelligence).
    Person 2 will implement the body of this function.
    Person 1 calls it after every STT result and feeds the returned string to TTS.
    """
    logger.info(f"[Person 2 stub] Processing utterance for call {call_sid}: '{transcript}' in {language}")
    # Placeholder response so the pipeline runs end-to-end without Person 2
    return "I heard you. What else would you like to order?"

@router.websocket("/stream")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    call_sid = None
    stream_sid = None
    
    # Audio buffering logic
    # Justification for fixed window: 
    # We use a fixed window (e.g., ~3 seconds = 150 chunks of 20ms) to accumulate audio.
    # This avoids relying on `audioop` for VAD (Voice Activity Detection), which was deprecated 
    # in Python 3.11 and removed in 3.13, keeping our application compatible with Python 3.11+ 
    # without adding external C-dependencies like WebRTC VAD.
    audio_buffer = bytearray()
    CHUNK_LIMIT = 150 # 150 * 20ms = 3000ms (3 seconds)
    
    try:
        while True:
            message = await websocket.receive_text()
            data = json.loads(message)
            
            if data['event'] == 'start':
                stream_sid = data['start']['streamSid']
                call_sid = data['start']['callSid']
                logger.info(f"Started audio stream for call {call_sid}, stream {stream_sid}")
                
                # Play initial greeting if stored in session
                session = session_store.get_session(call_sid)
                if session and session.order_buffer:
                    greeting = session.order_buffer.pop(0)
                    asyncio.create_task(play_tts(websocket, stream_sid, call_sid, greeting, session.language or "en-IN"))
                
            elif data['event'] == 'media':
                payload = data['media']['payload']
                audio_bytes = base64.b64decode(payload)
                audio_buffer.extend(audio_bytes)
                
                # Check if buffer is full (utterance-sized)
                if len(audio_buffer) >= CHUNK_LIMIT * 160: # 160 bytes per 20ms chunk
                    # 1. Take a copy of the buffer and clear it
                    utterance_audio = bytes(audio_buffer)
                    audio_buffer.clear()
                    
                    # Process asynchronously to avoid blocking the WebSocket receive loop
                    asyncio.create_task(handle_utterance(websocket, stream_sid, call_sid, utterance_audio))
                    
            elif data['event'] == 'stop':
                logger.info(f"Stream {stream_sid} stopped")
                break
                
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for call {call_sid}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")

async def handle_utterance(websocket: WebSocket, stream_sid: str, call_sid: str, audio_bytes: bytes):
    """
    Handles a single utterance buffer: STT -> Agent Logic -> TTS -> Send to Twilio
    """
    session = session_store.get_session(call_sid)
    if not session:
        logger.warning(f"No session found for call {call_sid}")
        return

    # 1. Sarvam AI STT
    stt_result = await recognize_speech(audio_bytes)
    transcript = stt_result.get("transcript", "").strip()
    confidence = stt_result.get("confidence", 1.0)
    detected_lang = stt_result.get("language_code")
    
    if not transcript:
        return # Ignore empty transcripts
        
    logger.info(f"STT Transcript: {transcript} (confidence: {confidence})")
    
    # 2. Language Detection (on first utterance)
    if session.language is None:
        session.language = determine_language(detected_lang)
        session_store.update_session(call_sid, session)
        logger.info(f"Set session language to {session.language}")

    # 3. Call Agent Service
    try:
        import httpx
        async with httpx.AsyncClient() as client:
            agent_res = await client.post("http://localhost:4000/agent/process-turn", json={
                "callSid": call_sid,
                "userMessage": transcript,
                "sttConfidence": confidence
            })
            agent_res.raise_for_status()
            agent_data = agent_res.json()
            
            response_text = agent_data.get("reply")
            agent_type = agent_data.get("type")
            
            # 4. Update Backend Transcript
            if session.call_id:
                # User entry
                await client.post("http://localhost:8001/api/call/update-transcript", json={
                    "call_id": session.call_id,
                    "entry": {"role": "user", "message": transcript}
                })
                # Bot entry
                await client.post("http://localhost:8001/api/call/update-transcript", json={
                    "call_id": session.call_id,
                    "entry": agent_data.get("transcriptEntry", {"role": "bot", "message": response_text})
                })

            # 5. Handle Specialized Agent Types (Confirmed, Escalated)
            if agent_type == "confirmed" and "orderPayload" in agent_data:
                p = agent_data["orderPayload"]
                # Create Order
                ord_res = await client.post("http://localhost:8001/api/order/create", json={
                    "customer_id": session.customer_id,
                    "call_id": session.call_id
                })
                if ord_res.is_success:
                    order_id = ord_res.json().get("id")
                    # Add Item
                    await client.post("http://localhost:8001/api/order/add-item", json={
                        "order_id": order_id,
                        "item_name": p.get("item"),
                        "quantity": p.get("quantity"),
                        "unit_price": p.get("unitPrice")
                    })
                    # Confirm Order
                    await client.post("http://localhost:8001/api/order/confirm", json={"order_id": order_id})
                    logger.info(f"Order confirmed and created in backend for call {call_sid}")

            elif agent_type == "escalated":
                logger.warning(f"Agent escalated call {call_sid}. Reason: {agent_data.get('reason')}")
                session.escalation_flag = True
                session_store.update_session(call_sid, session)
                # Play escalation message then hang up (TTS handled below)
                asyncio.create_task(delayed_hangup(call_sid, 5))

            elif agent_type == "cancelled":
                asyncio.create_task(delayed_hangup(call_sid, 3))

            # 6. Play TTS
            await play_tts(websocket, stream_sid, call_sid, response_text, session.language)

    except Exception as e:
        logger.error(f"Error in agent processing: {e}")
        error_msg = "I'm sorry, I encountered an error. Please wait while I connect you to an agent."
        await play_tts(websocket, stream_sid, call_sid, error_msg, session.language or "en-IN")
        hangup_call(call_sid)

async def delayed_hangup(call_sid, delay):
    await asyncio.sleep(delay)
    hangup_call(call_sid)

async def play_tts(websocket: WebSocket, stream_sid: str, call_sid: str, text: str, language: str):
    """
    Generate TTS and stream back to Twilio.
    """
    try:
        tts_audio_bytes = await generate_speech(text, language)
        if tts_audio_bytes:
            payload = base64.b64encode(tts_audio_bytes).decode('utf-8')
            
            message = {
                "event": "media",
                "streamSid": stream_sid,
                "media": {
                    "payload": payload
                }
            }
            await websocket.send_text(json.dumps(message))
    except Exception as e:
        logger.error(f"Error in TTS playback: {e}")
        hangup_call(call_sid)
