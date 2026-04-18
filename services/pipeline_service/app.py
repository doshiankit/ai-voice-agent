"""
Pipeline Service — port 8004
Single endpoint for FreeSWITCH: receives audio, runs STT → Agent → TTS internally,
returns audio. One network hop instead of three.
"""

import asyncio
import logging
import os
import tempfile
import time
import httpx
from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from dotenv import load_dotenv
load_dotenv("/root/ai-voice-agent/.env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [pipeline] %(message)s")
log = logging.getLogger(__name__)

app = FastAPI(title="Pipeline Service", version="1.0.0")

# Internal service URLs (localhost — no network cost)
STT_URL   = os.getenv("STT_URL",   "http://127.0.0.1:8001")
AGENT_URL = os.getenv("AGENT_URL", "http://127.0.0.1:8003")
TTS_URL   = os.getenv("TTS_URL",   "http://127.0.0.1:8002")

# Shared async HTTP client — keep connections alive across requests
_client: httpx.AsyncClient | None = None

@app.on_event("startup")
async def startup():
    global _client
    _client = httpx.AsyncClient(timeout=60.0)
    log.info("Pipeline service started — STT=%s  Agent=%s  TTS=%s",
             STT_URL, AGENT_URL, TTS_URL)

@app.on_event("shutdown")
async def shutdown():
    if _client:
        await _client.aclose()


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/pipeline")
async def pipeline(
    audio: UploadFile = File(..., description="WAV audio recorded by FreeSWITCH"),
    session_id: str = Form(default="", description="FreeSWITCH call UUID"),
    caller_id: str = Form(default="", description="Caller number"),
):
    """
    Full STT → Agent → TTS pipeline in one call.
    Returns the TTS audio file directly.
    """
    t0 = time.perf_counter()
    log.info("Pipeline request  session=%s  caller=%s  file=%s",
             session_id, caller_id, audio.filename)

    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(400, "Empty audio file")

    # ── Step 1: STT ────────────────────────────────────────────────────────────
    t1 = time.perf_counter()
    stt_resp = await _client.post(
        f"{STT_URL}/transcribe",
        files={"file": (audio.filename, audio_bytes, audio.content_type or "audio/wav")},
        data={"session_id": session_id},
    )
    if stt_resp.status_code != 200:
        log.error("STT failed: %s", stt_resp.text)
        raise HTTPException(502, f"STT service error: {stt_resp.text}")

    transcript = stt_resp.json().get("text", "").strip()
    log.info("STT done  %.2fs  text=%r", time.perf_counter() - t1, transcript[:80])

    if not transcript:
        # Silence or unrecognised audio — return a canned "sorry" audio
        return await _tts_canned(session_id)

    # ── Step 2: Agent ──────────────────────────────────────────────────────────
    t2 = time.perf_counter()
    agent_resp = await _client.post(
        f"{AGENT_URL}/chat",
        json={"text": transcript, "conversation_id": session_id},
    )
    if agent_resp.status_code != 200:
        log.error("Agent failed: %s", agent_resp.text)
        raise HTTPException(502, f"Agent service error: {agent_resp.text}")

    reply_text = agent_resp.json().get("response", "").strip()
    log.info("Agent done  %.2fs  reply=%r", time.perf_counter() - t2, reply_text[:80])

    # ── Step 3: TTS ────────────────────────────────────────────────────────────
    t3 = time.perf_counter()
    tts_resp = await _client.post(
        f"{TTS_URL}/synthesize",
        params={"text": reply_text, "session_id": session_id},
    )
    if tts_resp.status_code != 200:
        log.error("TTS failed: %s", tts_resp.text)
        raise HTTPException(502, f"TTS service error: {tts_resp.text}")

    audio_out = tts_resp.content
    log.info("TTS done  %.2fs  bytes=%d", time.perf_counter() - t3, len(audio_out))

    # ── Write to temp file and return ─────────────────────────────────────────
    suffix = ".wav"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix,
                                      prefix=f"pipeline_{session_id}_")
    tmp.write(audio_out)
    tmp.close()

    total = time.perf_counter() - t0
    log.info("Pipeline complete  %.2fs total  session=%s", total, session_id)

    return FileResponse(
        tmp.name,
        media_type="audio/wav",
        filename=f"response_{session_id}{suffix}",
        headers={"X-Pipeline-Duration": f"{total:.3f}",
                 "X-Transcript": transcript[:200]},
        background=_cleanup(tmp.name),
    )


async def _tts_canned(session_id: str):
    """Return TTS of a fallback message when STT yields nothing."""
    tts_resp = await _client.post(
        f"{TTS_URL}/synthesize",
        json={"text": "Sorry, I didn't catch that. Could you please repeat?",
              "session_id": session_id},
    )
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav",
                                      prefix=f"pipeline_{session_id}_silence_")
    tmp.write(tts_resp.content)
    tmp.close()
    return FileResponse(tmp.name, media_type="audio/wav",
                        background=_cleanup(tmp.name))


class _cleanup:
    """Background task to delete temp file after response is sent."""
    def __init__(self, path: str):
        self.path = path

    async def __call__(self):
        await asyncio.sleep(5)
        try:
            os.unlink(self.path)
        except OSError:
            pass


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("pipeline_service:app", host="0.0.0.0", port=8004,
                workers=1, log_level="info")
