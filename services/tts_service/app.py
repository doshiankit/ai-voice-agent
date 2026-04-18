from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import Response, JSONResponse
import base64
import os
import time
import uuid
import logging
import threading
import struct
import numpy as np
import piper
from dotenv import load_dotenv
load_dotenv("/root/ai-voice-agent/.env")

APP_NAME = "tts-service"
DEFAULT_VOICE = os.getenv("VOICE_PATH", "app/voices/en_US-amy-medium.onnx")
MAX_TEXT_LEN = int(os.getenv("MAX_TEXT_LEN", "800"))  # protect CPU
DEFAULT_FORMAT = os.getenv("DEFAULT_FORMAT", "wav")   # wav | json | slin
DEFAULT_SR = int(os.getenv("DEFAULT_SAMPLE_RATE", "22050"))  # output SR

# NEW: naturalness defaults (tweak these)
DEFAULT_LENGTH_SCALE = float(os.getenv("DEFAULT_LENGTH_SCALE", "1.1"))  # >1 slower, <1 faster
DEFAULT_NOISE_SCALE  = float(os.getenv("DEFAULT_NOISE_SCALE", "0.5"))   # lower can sound cleaner
DEFAULT_NOISE_W      = float(os.getenv("DEFAULT_NOISE_W", "0.8"))       # variation

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger(APP_NAME)

app = FastAPI(title="TTS Service", version="1.0.0")

_engine_lock = threading.Lock()
tts_engine = None
voice_path_loaded = None


def _load_engine(path: str):
    global tts_engine, voice_path_loaded
    with _engine_lock:
        if tts_engine is not None and voice_path_loaded == path:
            return
        log.info("Loading Piper voice: %s", path)
        tts_engine = piper.PiperVoice.load(path)
        voice_path_loaded = path
        log.info("Piper voice ready: %s", path)


def pcm16_to_wav_bytes(pcm16: bytes, sample_rate: int, channels: int = 1) -> bytes:
    byte_rate = sample_rate * channels * 2
    block_align = channels * 2
    data_size = len(pcm16)
    riff_size = 36 + data_size
    return b"".join([
        b"RIFF",
        struct.pack("<I", riff_size),
        b"WAVE",
        b"fmt ",
        struct.pack("<IHHIIHH", 16, 1, channels, sample_rate, byte_rate, block_align, 16),
        b"data",
        struct.pack("<I", data_size),
        pcm16
    ])


def resample_pcm16_mono(pcm16: bytes, in_sr: int, out_sr: int) -> bytes:
    if in_sr == out_sr:
        return pcm16

    x = np.frombuffer(pcm16, dtype=np.int16).astype(np.float32)
    if len(x) < 2:
        return pcm16

    ratio = out_sr / float(in_sr)
    n_out = int(len(x) * ratio)

    idx = np.linspace(0, len(x) - 1, n_out)
    x0 = np.floor(idx).astype(np.int32)
    x1 = np.clip(x0 + 1, 0, len(x) - 1)
    frac = (idx - x0).astype(np.float32)
    y = x[x0] * (1.0 - frac) + x[x1] * frac

    y = np.clip(y, -32768, 32767).astype(np.int16)
    return y.tobytes()


def synthesize_pcm16(text: str, voice_path: str, length_scale: float, noise_scale: float, noise_w: float):
    if not text or not text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty.")
    text = text.strip()

    if len(text) > MAX_TEXT_LEN:
        raise HTTPException(status_code=413, detail=f"Text too long. Max {MAX_TEXT_LEN} chars.")

    # Safety clamps (avoid crazy values)
    if length_scale < 0.5 or length_scale > 2.0:
        raise HTTPException(status_code=400, detail="length_scale must be between 0.5 and 2.0")
    if noise_scale < 0.0 or noise_scale > 1.5:
        raise HTTPException(status_code=400, detail="noise_scale must be between 0.0 and 1.5")
    if noise_w < 0.0 or noise_w > 2.0:
        raise HTTPException(status_code=400, detail="noise_w must be between 0.0 and 2.0")

    _load_engine(voice_path)

    # Piper API versions differ slightly; try kwargs, fallback to plain call
    try:
        chunks = list(tts_engine.synthesize(text, length_scale=length_scale, noise_scale=noise_scale, noise_w=noise_w))
    except TypeError:
        chunks = list(tts_engine.synthesize(text))

    if not chunks:
        raise HTTPException(status_code=500, detail="No audio generated")

    pcm_parts = []
    sr = chunks[0].sample_rate
    ch = getattr(chunks[0], "sample_channels", 1)

    for c in chunks:
        if hasattr(c, "audio_int16_bytes") and c.audio_int16_bytes:
            pcm_parts.append(c.audio_int16_bytes)
        elif hasattr(c, "audio_int16_array") and c.audio_int16_array is not None:
            pcm_parts.append(c.audio_int16_array.astype(np.int16).tobytes())
        elif hasattr(c, "audio_float_array") and c.audio_float_array is not None:
            pcm_parts.append((c.audio_float_array * 32767).astype(np.int16).tobytes())
        else:
            arr = np.array(c)
            if arr.dtype.kind == "f":
                pcm_parts.append((arr * 32767).astype(np.int16).tobytes())
            else:
                pcm_parts.append(arr.astype(np.int16).tobytes())

    pcm16 = b"".join(pcm_parts)

    # Force mono if needed
    if ch != 1:
        a = np.frombuffer(pcm16, dtype=np.int16)
        a = a.reshape(-1, ch).mean(axis=1).astype(np.int16)
        pcm16 = a.tobytes()
        ch = 1

    return pcm16, sr, ch


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    rid = request.headers.get("x-request-id", str(uuid.uuid4()))
    start = time.time()
    try:
        response = await call_next(request)
    finally:
        dur_ms = int((time.time() - start) * 1000)
        log.info("rid=%s method=%s path=%s status=%s dur_ms=%s",
                 rid, request.method, request.url.path, getattr(response, "status_code", "NA"), dur_ms)
    response.headers["x-request-id"] = rid
    return response


@app.api_route("/synthesize", methods=["GET", "POST"])
async def synthesize(
    text: str = Query(..., description="Text to synthesize"),
    format: str = Query(DEFAULT_FORMAT, description="wav | json | slin"),
    sample_rate: int = Query(DEFAULT_SR, description="Output sample rate (e.g., 8000, 16000, 22050)"),
    voice: str = Query("", description="Optional voice onnx filename inside app/voices/"),

    # NEW: tuning params
    length_scale: float = Query(DEFAULT_LENGTH_SCALE, description="Speech speed. >1 slower, <1 faster"),
    noise_scale: float  = Query(DEFAULT_NOISE_SCALE,  description="Expressiveness/variation"),
    noise_w: float      = Query(DEFAULT_NOISE_W,      description="Variation weight"),
):
    if voice:
        voice_path = os.path.join("app/voices", voice)
    else:
        voice_path = DEFAULT_VOICE

    if not os.path.exists(voice_path):
        raise HTTPException(status_code=404, detail=f"Voice model not found: {voice_path}")

    pcm16, in_sr, ch = synthesize_pcm16(text, voice_path, length_scale, noise_scale, noise_w)

    if sample_rate not in (8000, 16000, 22050, 24000, 44100, 48000):
        raise HTTPException(status_code=400, detail="Unsupported sample_rate.")
    pcm16 = resample_pcm16_mono(pcm16, in_sr, sample_rate)

    fmt = (format or "wav").lower()

    if fmt == "slin":
        return Response(content=pcm16, media_type="application/octet-stream")

    wav_bytes = pcm16_to_wav_bytes(pcm16, sample_rate, ch)

    if fmt == "wav":
        return Response(content=wav_bytes, media_type="audio/wav")

    if fmt == "json":
        audio_b64 = base64.b64encode(wav_bytes).decode("utf-8")
        return JSONResponse(content={
            "audio": audio_b64,
            "format": "wav",
            "sample_rate": sample_rate,
            "channels": ch,
            "text_length": len(text),
            "audio_size_bytes": len(wav_bytes),
            "voice": os.path.basename(voice_path),
            "length_scale": length_scale,
            "noise_scale": noise_scale,
            "noise_w": noise_w,
        })

    raise HTTPException(status_code=400, detail="Invalid format. Use wav|json|slin")


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "TTS"}


@app.get("/ready")
async def ready():
    return {
        "ready": True if tts_engine is not None else False,
        "voice_path": voice_path_loaded or DEFAULT_VOICE,
        "max_text_len": MAX_TEXT_LEN,
        "default_format": DEFAULT_FORMAT,
        "default_sample_rate": DEFAULT_SR,
        "default_length_scale": DEFAULT_LENGTH_SCALE,
        "default_noise_scale": DEFAULT_NOISE_SCALE,
        "default_noise_w": DEFAULT_NOISE_W,
    }


@app.get("/voices")
async def voices():
    voices_dir = "app/voices"
    if not os.path.isdir(voices_dir):
        return {"voices": []}
    return {"voices": sorted([f for f in os.listdir(voices_dir) if f.endswith(".onnx")])}
