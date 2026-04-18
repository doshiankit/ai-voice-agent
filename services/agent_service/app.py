#!/usr/bin/env python3
"""
AI Agent Service - VoIP/FreeSWITCH Support Agent (TTS‑optimised)
Uses Groq LLM for intelligent, contextual responses.
"""
from dotenv import load_dotenv
load_dotenv("/root/ai-voice-agent/.env")

import os
import time
import uuid
import re
from typing import Optional, Dict, Any, List

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from groq import Groq

app = FastAPI(title="AI Agent Service", version="2.2.0")

# ------------------------------------------------------------------
# Groq Setup
# ------------------------------------------------------------------
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
print(f"[DEBUG] GROQ_API_KEY loaded: {GROQ_API_KEY[:8]}...{GROQ_API_KEY[-4:] if GROQ_API_KEY else 'NONE'}", flush=True)
if not GROQ_API_KEY:
    raise RuntimeError("GROQ_API_KEY environment variable is not set")

client = Groq(api_key=GROQ_API_KEY)
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
SYSTEM_PROMPT = os.getenv(
    "AGENT_SYSTEM_PROMPT",
    "You are a helpful voice assistant. Keep responses concise and clear for phone conversations."
)
# ------------------------------------------------------------------
# Data Models
# ------------------------------------------------------------------
class ChatRequest(BaseModel):
    text: str
    conversation_id: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    conversation_id: Optional[str] = None

# ------------------------------------------------------------------
# Conversation Memory (in‑memory, TTL 30 minutes)
# ------------------------------------------------------------------
CONV_TTL_SECONDS = 60 * 30
conversations: Dict[str, Dict[str, Any]] = {}

def _now() -> int:
    return int(time.time())

def _gc_conversations():
    cutoff = _now() - CONV_TTL_SECONDS
    dead = [cid for cid, st in conversations.items() if st.get("updated_at", 0) < cutoff]
    for cid in dead:
        conversations.pop(cid, None)

def _get_or_create_conversation(conversation_id: Optional[str]) -> str:
    _gc_conversations()
    cid = (conversation_id or "").strip()
    if not cid:
        cid = str(uuid.uuid4())
    if cid not in conversations:
        conversations[cid] = {
            "created_at": _now(),
            "updated_at": _now(),
            "history": [
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT
                }
            ],
            "turns": 0
        }
    return cid

def _update_conversation(cid: str):
    conversations[cid]["updated_at"] = _now()
    conversations[cid]["turns"] += 1

def _add_to_history(cid: str, role: str, content: str):
    conversations[cid]["history"].append({"role": role, "content": content})

# ------------------------------------------------------------------
# TTS‑friendly Text Cleanup
# ------------------------------------------------------------------
def _tts_friendly(text: str) -> str:
    """
    Convert LLM output into something a TTS engine can speak clearly.
    - Removes markdown, quotes, and excessive newlines.
    - Replaces numbered lists with "First, ... Second, ..."
    """
    # Remove markdown code blocks and backticks
    text = re.sub(r'```.*?```', '', text, flags=re.DOTALL)
    text = re.sub(r'`([^`]*)`', r'\1', text)
    text = text.replace('*', '').replace('_', '').replace('"', '')

    lines = text.split('\n')
    spoken_lines = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Convert "1) command" → "First, command"
        match = re.match(r'^(\d+)[\)\.]\s*(.*)$', line)
        if match:
            num = int(match.group(1))
            rest = match.group(2)
            prefixes = {1: "First", 2: "Second", 3: "Third", 4: "Fourth", 5: "Fifth"}
            prefix = prefixes.get(num, f"Step {num}")
            line = f"{prefix}, {rest}"
        spoken_lines.append(line)

    return ". ".join(spoken_lines)

# ------------------------------------------------------------------
# LLM Call
# ------------------------------------------------------------------
def _get_llm_response(cid: str, user_text: str) -> str:
    """Send user message to Groq LLM and return TTS‑friendly reply."""
    history = conversations[cid]["history"]

    # Add user message
    _add_to_history(cid, "user", user_text)

    try:
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=history,          # entire conversation context
            max_tokens=200,
            temperature=0.5,
        )
        reply = response.choices[0].message.content

        # Add assistant reply to history
        _add_to_history(cid, "assistant", reply)

        return _tts_friendly(reply)

    except Exception as e:
        print(f"[GROQ ERROR] {type(e).__name__}: {str(e)}", flush=True)
        # Fallback in case of API error
        fallback = "I'm having trouble reaching the language model right now. Please try again in a moment."
        _add_to_history(cid, "assistant", fallback)
        return fallback

# ------------------------------------------------------------------
# Endpoint
# ------------------------------------------------------------------
@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    try:
        user_message = (request.text or "").strip()
        if not user_message:
            raise HTTPException(status_code=400, detail="Text cannot be empty")

        cid = _get_or_create_conversation(request.conversation_id)
        _update_conversation(cid)

        # Quick good‑bye detection (optional shortcut)
        if re.search(r'\b(bye|goodbye|thank you|thanks|that is all)\b', user_message.lower()):
            response_text = _tts_friendly(
                "You're welcome. Goodbye. If the issue returns, just describe what's happening."
            )
            _add_to_history(cid, "assistant", response_text)
            return ChatResponse(response=response_text, conversation_id=cid)

        # Call LLM for real response
        t0 = time.time()
        reply = _get_llm_response(cid, user_message)
        print(f"[LATENCY] LLM: {time.time()-t0:.2f}s", flush=True)
        return ChatResponse(response=reply, conversation_id=cid)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")

@app.get("/health")
async def health_check():
    return {"status": "healthy", "active_conversations": len(conversations)}
