import base64

try:
    import audioop
except ImportError:
    audioop = None

def decode_twilio_payload(payload: str) -> bytes:
    """
    Decodes the base64 payload received from Twilio's WebSocket.
    Twilio sends audio as 8kHz mulaw encoded in base64.
    """
    return base64.b64decode(payload)

def encode_audio_for_twilio(audio_bytes: bytes) -> str:
    """
    Encodes audio bytes to base64 for sending to Twilio WebSocket.
    Twilio expects base64 encoded 8kHz mulaw.
    """
    return base64.b64encode(audio_bytes).decode('utf-8')

def convert_ulaw_to_pcm(ulaw_data: bytes) -> bytes:
    """
    Converts 8kHz mulaw audio to 16-bit PCM if required by downstream services.
    """
    if audioop is None:
        raise NotImplementedError("audioop module not available (removed in Python 3.13).")
    return audioop.ulaw2lin(ulaw_data, 2)

def convert_pcm_to_ulaw(pcm_data: bytes) -> bytes:
    """
    Converts 16-bit PCM back to 8kHz mulaw.
    """
    if audioop is None:
        raise NotImplementedError("audioop module not available.")
    return audioop.lin2ulaw(pcm_data, 2)
