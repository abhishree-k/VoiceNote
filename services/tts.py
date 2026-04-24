import httpx
import logging
import base64
from config import SARVAM_API_KEY

logger = logging.getLogger(__name__)

async def generate_speech(text: str, language_code: str) -> bytes:
    """
    POSTs to Sarvam's text-to-speech endpoint.
    Accepts text and language code.
    Returns audio bytes in mulaw format compatible with Twilio's <Stream>.
    """
    url = "https://api.sarvam.ai/text-to-speech"
    
    headers = {
        "api-subscription-key": SARVAM_API_KEY,
        "Content-Type": "application/json"
    }
    
    payload = {
        "inputs": [text],
        "target_language_code": language_code,
        "speaker": "meera", # Default voice
        "model": "bulbul:v1", # Standard TTS model for Sarvam
        "speech_sample_rate": 8000,
        "enable_preprocessing": True,
        "pace": 1.0
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=payload, timeout=10.0)
            response.raise_for_status()
            result = response.json()
            
            # Sarvam returns base64 string in 'audios' array
            # Assuming we can request 8000Hz mulaw or we get base64 encoded wav/pcm
            # If we need mulaw explicitly, we could convert it, but Twilio <Stream> 
            # requires base64 encoded 8000Hz mulaw strings, and this function
            # returns the raw bytes (which will be base64 encoded before sending to Twilio).
            audios = result.get("audios", [])
            if audios and audios[0]:
                audio_base64 = audios[0]
                return base64.b64decode(audio_base64)
            return b""
    except Exception as e:
        logger.error(f"Sarvam TTS API error: {e}")
        raise e
