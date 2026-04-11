#!/usr/bin/env python3
"""
AI Agent Service - VoIP/FreeSWITCH Support Agent (TTS‑optimised)
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
import time
import uuid
import re

app = FastAPI(title="AI Agent Service", version="2.1.0")

class ChatRequest(BaseModel):
    text: str
    conversation_id: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    conversation_id: Optional[str] = None

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
            "turns": 0,
            "slots": {"issue": None, "platform": None, "impact": None}
        }
    return cid

def _update_conversation(cid: str):
    conversations[cid]["updated_at"] = _now()
    conversations[cid]["turns"] += 1

def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())

def _contains_any(text: str, words):
    return any(w in text for w in words)

def _is_end_user(text: str) -> bool:
    return _contains_any(text, ["bye", "goodbye", "thank you", "thanks", "that is all"])

def _detect_domain_issue(text: str) -> str:
    # Catch all common mis‑transcriptions of FreeSWITCH
    if _contains_any(text, [
        "freeswitch", "free switch", "free speech", "pre page", "pre pitch",
        "free swich", "all way switch", "all way"
    ]):
        return "check_freeswitch_running"

    if _contains_any(text, ["no calls", "calls are down", "calls down", "calls not running", "call down"]):
        return "calls_down"

    if _contains_any(text, ["sip", "registration", "registered", "unregistered", "sofia"]):
        return "sip_registration"

    if _contains_any(text, ["no audio", "one way audio", "rtp", "media"]):
        return "no_audio"

    if _contains_any(text, ["cpu high", "memory", "ram", "disk full", "load"]):
        return "system_resources"

    if _contains_any(text, ["logs", "error", "debug"]):
        return "check_logs"

    if _contains_any(text, ["help", "support", "assist"]):
        return "general_support"

    return "unknown"

def _tts_friendly(text: str) -> str:
    """
    Convert technical text into something a TTS engine can speak clearly.
    - Replace newlines with pauses (using periods).
    - Remove quotes.
    - Optionally add "first", "second" etc. if it's a list.
    """
    # Replace numbered list with "First, ... Second, ..."
    lines = text.split('\n')
    spoken_lines = []
    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
        # If line starts with a number and a parenthesis, convert
        if re.match(r'^\d+[\)\.]', line):
            # e.g., "1) systemctl ..." -> "First, systemctl ..."
            number = int(re.match(r'^(\d+)[\)\.]', line).group(1))
            if number == 1:
                prefix = "First"
            elif number == 2:
                prefix = "Second"
            elif number == 3:
                prefix = "Third"
            elif number == 4:
                prefix = "Fourth"
            elif number == 5:
                prefix = "Fifth"
            else:
                prefix = f"Step {number}"
            line = re.sub(r'^\d+[\)\.]\s*', prefix + ', ', line)
        spoken_lines.append(line)
    # Join with ". " to create natural pauses
    return ". ".join(spoken_lines).replace('"', '')

def _reply_for_intent(intent: str) -> str:
    if intent in ("check_freeswitch_running", "calls_down", "general_support"):
        raw = (
            "To confirm FreeSWITCH is running, run these commands on the server:\n"
            "1) systemctl status freeswitch --no-pager -l\n"
            "2) fs_cli -x \"status\"\n"
            "3) fs_cli -x \"sofia status\"\n"
            "4) ss -lntup | grep -E \"5060|5061|8021|freeswitch\"\n"
            "5) tail -n 200 /usr/local/freeswitch/log/freeswitch.log\n\n"
            "Tell me: are ALL calls down, or only SOME calls?"
        )
        return _tts_friendly(raw)

    if intent == "sip_registration":
        raw = (
            "To check SIP registrations:\n"
            "1) fs_cli -x \"sofia status\"\n"
            "2) fs_cli -x \"sofia status profile internal reg\"\n"
            "3) fs_cli -x \"sofia status profile internal\"\n\n"
            "Tell me the extension number and whether it shows as Registered."
        )
        return _tts_friendly(raw)

    if intent == "no_audio":
        raw = (
            "For no‑audio or one‑way audio:\n"
            "1) fs_cli -x \"show channels\"\n"
            "2) fs_cli -x \"uuid_dump <call_uuid>\"\n"
            "3) tcpdump -nni any udp portrange 10000-65000\n"
            "4) Check NAT settings: external_rtp_ip and external_sip_ip in sofia profile\n\n"
            "Tell me: is it one‑way audio or no audio both ways?"
        )
        return _tts_friendly(raw)

    if intent == "system_resources":
        raw = (
            "To check server resources:\n"
            "1) uptime\n"
            "2) free -h\n"
            "3) df -h\n"
            "4) top -o \%CPU\n"
            "5) journalctl -u freeswitch -n 200 --no-pager\n\n"
            "Tell me your CPU load and free memory."
        )
        return _tts_friendly(raw)

    if intent == "check_logs":
        raw = (
            "To check FreeSWITCH logs:\n"
            "1) tail -n 200 /usr/local/freeswitch/log/freeswitch.log\n"
            "2) grep -i \"error\\|crit\\|fail\" /usr/local/freeswitch/log/freeswitch.log | tail -n 50\n"
            "3) journalctl -u freeswitch -n 200 --no-pager\n\n"
            "If you paste the last 30 error lines, I can tell the exact cause."
        )
        return _tts_friendly(raw)

    # unknown
    return _tts_friendly(
        "I can help with FreeSWITCH and VoIP support. "
        "Please say one of these: "
        "1) FreeSWITCH service is down, "
        "2) Calls are not running, "
        "3) SIP registration issue, "
        "4) No audio issue. "
        "Then I will give exact commands."
    )

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    try:
        user_message = (request.text or "").strip()
        if not user_message:
            raise HTTPException(status_code=400, detail="Text cannot be empty")

        cid = _get_or_create_conversation(request.conversation_id)
        _update_conversation(cid)

        text = _norm(user_message)

        if _is_end_user(text):
            return ChatResponse(
                response=_tts_friendly(
                    "Okay. Goodbye. If the issue returns, tell me: calls down, no audio, or registration problem."
                ),
                conversation_id=cid
            )

        intent = _detect_domain_issue(text)
        response = _reply_for_intent(intent)

        return ChatResponse(response=response, conversation_id=cid)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")

@app.get("/health")
async def health_check():
    return {"status": "healthy", "active_conversations": len(conversations)}
