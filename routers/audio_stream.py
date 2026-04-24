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
    Handles a single utterance buffer: STT -> Logic -> TTS -> Send to Twilio
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
    
    # 2. Low-confidence flag
    if confidence < CONFIDENCE_THRESHOLD:
        logger.warning(f"Low confidence ({confidence}) for call {call_sid}. Escalating.")
        session.escalation_flag = True
        session_store.update_session(call_sid, session)
        # We can play a fallback message before hanging up
        fallback_msg = "I'm having trouble understanding. Let me transfer you to a human."
        await play_tts(websocket, stream_sid, call_sid, fallback_msg, session.language or "en-IN")
        hangup_call(call_sid)
        return

    # 3. Language Detection (on first utterance)
    if session.language is None:
        session.language = determine_language(detected_lang)
        session_store.update_session(call_sid, session)
        logger.info(f"Set session language to {session.language}")
        
        # Update Supabase
        if supabase:
            try:
                supabase.table("calls").update({"language": session.language}).eq("call_sid", call_sid).execute()
            except Exception as e:
                logger.error(f"Failed to update language in Supabase: {e}")
                
    # 4. Call Person 2's Logic (Process Utterance)
    # Pass conversation history (we'll just append the user's turn for now)
    session.conversation_history.append({"role": "user", "content": transcript})
    
    response_text = await process_utterance(call_sid, transcript, session.language)
    
    session.conversation_history.append({"role": "assistant", "content": response_text})
    session_store.update_session(call_sid, session)
    
    # 5. Sarvam AI TTS Integration
    await play_tts(websocket, stream_sid, call_sid, response_text, session.language)

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
