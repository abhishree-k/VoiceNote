import httpx
import logging
from config import SARVAM_API_KEY

logger = logging.getLogger(__name__)

async def recognize_speech(audio_bytes: bytes) -> dict:
    """
    POSTs buffered audio to Sarvam AI STT endpoint.
    Returns dict with transcript, language_code, and confidence.
    """
    url = "https://api.sarvam.ai/speech-to-text"
    
    headers = {
        "api-subscription-key": SARVAM_API_KEY,
    }
    
    files = {
        'file': ('audio.wav', audio_bytes, 'audio/wav')
    }
    
    # We pass 'saaras:v1' model as per Sarvam's STT API documentation
    data = {
        'model': 'saaras:v1'
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, files=files, data=data, timeout=10.0)
            response.raise_for_status()
            result = response.json()
            
            # Extract transcript text and confidence score
            # Sarvam may return language_code if it detects it, or we fallback to en-IN
            transcript = result.get("transcript", "")
            language_code = result.get("language_code", "en-IN")
            confidence = result.get("confidence", 1.0)
            
            return {
                "transcript": transcript,
                "language_code": language_code,
                "confidence": confidence
            }
    except Exception as e:
        logger.error(f"Sarvam STT API error: {e}")
        # In case of error, return empty values with 0 confidence to trigger failure handling
        return {
            "transcript": "",
            "language_code": "en-IN",
            "confidence": 0.0
        }
