#!/usr/bin/env python3
"""
STT Service using faster-whisper (CPU-optimised)
"""

import os
import tempfile
import subprocess
from typing import Optional
import numpy as np
import soundfile as sf
from scipy.signal import resample_poly
from math import gcd

os.environ["PATH"] = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:" + os.environ.get("PATH", "")

from fastapi import FastAPI, File, UploadFile, HTTPException, Query
from fastapi.responses import JSONResponse
from faster_whisper import WhisperModel

APP_TITLE = "STT Service"
WHISPER_MODEL_NAME = os.getenv("WHISPER_MODEL", "small")   # small is fast and accurate enough
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "25"))
ALLOWED_EXT = {".wav", ".mp3", ".m4a", ".flac", ".ogg", ".webm"}

app = FastAPI(title=APP_TITLE)

model = None
model_load_error: Optional[str] = None

# Common mis‑transcriptions for VoIP terms
CORRECTIONS = {
    "all way switch": "FreeSWITCH",
    "all way": "FreeSWITCH",
    "free switch": "FreeSWITCH",
    "freeswitch": "FreeSWITCH",
    "pre page": "FreeSWITCH",
    "pre pitch": "FreeSWITCH",
    "sip truck": "SIP trunk",
}

def _ext_ok(filename: str) -> bool:
    _, ext = os.path.splitext(filename.lower())
    return ext in ALLOWED_EXT

def _apply_corrections(text: str) -> str:
    for wrong, right in CORRECTIONS.items():
        text = text.replace(wrong, right)
    return text

def _preprocess_audio(input_path: str, output_path: str):
    """
    In-process resample to 16kHz mono.
    WHY: soundfile reads the WAV directly into a numpy array (no subprocess).
    scipy resample_poly does the rate conversion in-memory.
    Zero subprocess overhead — typically 5-10ms vs 100-120ms for ffmpeg fork.
    """
    data, orig_sr = sf.read(input_path, always_2d=True)

    # Mix down to mono if stereo
    if data.shape[1] > 1:
        data = data.mean(axis=1)
    else:
        data = data[:, 0]

    # Resample to 16kHz only if needed
    target_sr = 16000
    if orig_sr != target_sr:
        g = gcd(orig_sr, target_sr)
        data = resample_poly(data, target_sr // g, orig_sr // g).astype(np.float32)

    # Normalise amplitude (replaces volume=2 and highpass/lowpass roughly)
    peak = np.abs(data).max()
    if peak > 0:
        data = (data / peak * 0.95).astype(np.float32)

    sf.write(output_path, data, target_sr, subtype="PCM_16")
    
@app.on_event("startup")
def load_model():
    global model, model_load_error
    try:
        print(f"Loading faster-whisper model: {WHISPER_MODEL_NAME} (CPU int8)...")
        model = WhisperModel(WHISPER_MODEL_NAME, device="cpu", compute_type="int8")
        model_load_error = None
        print("Model loaded.")
    except Exception as e:
        model = None
        model_load_error = str(e)
        print(f"Failed to load model: {model_load_error}")

@app.post("/transcribe")
async def transcribe_audio(
    file: UploadFile = File(...),
    language: str = Query("en", description="Language code or 'auto'"),
    task: str = Query("transcribe", description="transcribe or translate"),
    beam_size: int = Query(5, ge=1, le=10),
):
    if model is None:
        raise HTTPException(status_code=500, detail=f"Model not loaded: {model_load_error}")

    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename")
    if not _ext_ok(file.filename):
        raise HTTPException(status_code=400, detail=f"Unsupported format. Allowed: {sorted(ALLOWED_EXT)}")
    if task not in ("transcribe", "translate"):
        raise HTTPException(status_code=400, detail="task must be 'transcribe' or 'translate'")

    content = await file.read()
    max_bytes = MAX_UPLOAD_MB * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(status_code=413, detail=f"File too large. Max {MAX_UPLOAD_MB} MB")

    tmp_path = None
    proc_path = None
    try:
        suffix = os.path.splitext(file.filename)[1].lower()
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        proc_path = tmp_path + "_proc.wav"
        _preprocess_audio(tmp_path, proc_path)

        whisper_lang = None if language.strip().lower() == "auto" else language.strip().lower()

        prompt = (
            "Technical support call about FreeSWITCH, VoIP, SIP trunk, "
            "pager, phone system, server down. The customer says FreeSWITCH."
        )

        segments, info = model.transcribe(
            proc_path,
            language=whisper_lang,
            task=task,
            beam_size=1,
            best_of=1,
            temperature=0.0,
            initial_prompt=prompt,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=300,speech_pad_ms=200),
            condition_on_previous_text=False
            word_timestamps=False
        )

        text = " ".join([seg.text for seg in segments]).strip()
        text = _apply_corrections(text)

        return JSONResponse(content={
            "text": text,
            "language": info.language,
            "task": task,
            "model": WHISPER_MODEL_NAME,
        })

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")
    finally:
        for p in [tmp_path, proc_path]:
            if p and os.path.exists(p):
                try:
                    os.unlink(p)
                except Exception:
                    pass

@app.get("/health")
async def health_check():
    return {
        "status": "healthy" if model is not None else "unhealthy",
        "model_loaded": model is not None,
        "model": WHISPER_MODEL_NAME,
        "error": model_load_error,
        "max_upload_mb": MAX_UPLOAD_MB,
    }
