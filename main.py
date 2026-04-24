import uvicorn
from fastapi import FastAPI
from routers import twilio_webhook, audio_stream
from config import PORT

app = FastAPI(title="Automaton AI - Voice Pipeline (Person 1)")

# Mount routers
app.include_router(twilio_webhook.router)
app.include_router(audio_stream.router)

@app.get("/")
async def health_check():
    return {"status": "ok", "message": "Automaton AI Voice Pipeline is running."}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=PORT, reload=True)
