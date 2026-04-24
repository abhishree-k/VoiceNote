# Automaton AI - Voice Pipeline (Person 1)

This repository contains the Person 1 implementation for Automaton AI: a multilingual voice order acceptance bot.
It handles Twilio voice webhooks, WebSockets for audio streaming, Sarvam AI STT/TTS integrations, and Supabase data writes.

## How to Run Locally

1. **Install dependencies:**
   Make sure you have Python 3.11+ installed.
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure Environment Variables:**
   Copy `.env.example` to `.env` and fill in your credentials.
   ```bash
   cp .env.example .env
   ```

3. **Start the FastAPI Server:**
   ```bash
   python main.py
   # Or using uvicorn directly:
   # uvicorn main:app --host 0.0.0.0 --port 8000 --reload
   ```

## Exposing via ngrok for Twilio Webhooks

Twilio needs a public URL to send incoming call events and stream audio via WebSockets.

1. Install and start [ngrok](https://ngrok.com/):
   ```bash
   ngrok http 8000
   ```

2. Copy the `Forwarding` URL that starts with `https://` (e.g., `https://1234-abcd.ngrok-free.app`).
3. Update your `.env` file, setting `NGROK_URL` to the **WebSocket** protocol version of this URL:
   ```env
   NGROK_URL=wss://1234-abcd.ngrok-free.app
   ```
   *(Note: The codebase automatically handles HTTP/WS replacements where necessary, so just provide the `wss://` or `https://` base URL).*

## Twilio Configuration

In the Twilio Console (Phone Numbers -> Manage -> Active Numbers):
- Under **Voice & Fax**, set **A CALL COMES IN** to **Webhook**: `https://1234-abcd.ngrok-free.app/incoming-call` (HTTP POST).
- The server will automatically respond with TwiML `<Connect><Stream>` directing the audio to your WebSocket endpoint `/stream`.

## Audio Format Contract

- **Twilio -> Application:** Twilio streams inbound audio via WebSockets in `base64` encoded chunks of `8000Hz mulaw` audio (each payload is 160 bytes / 20ms of audio).
- **Buffering:** We accumulate 150 chunks (3 seconds) to capture an utterance. (No external VAD dependencies used to maintain Python 3.11+ compatibility without C-extensions).
- **Application -> Sarvam STT:** The raw buffer is POSTed to Sarvam `speech-to-text`.
- **Sarvam TTS -> Application:** The TTS returns `base64` encoded audio.
- **Application -> Twilio:** We send the TTS output back to Twilio over the WebSocket as `base64` encoded `8000Hz mulaw` for playback to the caller.

## Integration with Person 2 (Order Intelligence)

Person 2 is responsible for the LLM logic (Claude API + Order matching).
- Look in `routers/audio_stream.py` for the `process_utterance` function.
- Person 2 should modify this stub function to receive the `transcript`, call Claude, and return the `response_text`.
