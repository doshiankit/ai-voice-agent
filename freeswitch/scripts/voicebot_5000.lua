-- voicebot_5000.lua
-- FreeSWITCH Lua Voicebot: Record -> Pipeline -> Playback
-- Single HTTP call to pipeline service handles STT + LLM + TTS internally.

local function log(level, msg)
  freeswitch.consoleLog(level, "[voicebot] " .. tostring(msg) .. "\n")
end

local function shell(cmd)
  local f = io.popen(cmd .. " 2>&1")
  if not f then return "", 1 end
  local out = f:read("*a") or ""
  local ok, why, rc = f:close()
  rc = rc or 0
  return out, rc
end

local function trim(s)
  s = tostring(s or "")
  return (s:gsub("^%s+", ""):gsub("%s+$", ""))
end

local function file_size(path)
  local f = io.open(path, "rb")
  if not f then return 0 end
  local sz = f:seek("end")
  f:close()
  return tonumber(sz) or 0
end

local function rm_file(path)
  if path and path ~= "" then
    os.remove(path)
  end
end

local function lower(s)
  return string.lower(tostring(s or ""))
end

local function should_end(text)
  local t = lower(text)
  return t:find("bye", 1, true)
      or t:find("goodbye", 1, true)
      or t:find("thank you", 1, true)
      or t:find("thanks", 1, true)
      or t:find("stop", 1, true)
end

-- ── Load .env ─────────────────────────────────────────────────
local function load_env(filepath)
  local file = io.open(filepath, "r")
  if not file then return {} end
  local env = {}
  for line in file:lines() do
    line = line:match("^%s*(.-)%s*$")
    if line ~= "" and not line:match("^#") then
      local key, value = line:match("^([%w_]+)%s*=%s*(.+)$")
      if key and value then
        value = value:gsub("^['\"]", ""):gsub("['\"]$", "")
        env[key] = value
      end
    end
  end
  file:close()
  return env
end

local env_vars = {}
local env_paths = {
  "/root/ai-voice-agent/.env",
  "/etc/freeswitch/.env",
  "/usr/local/freeswitch/conf/.env",
}
for _, p in ipairs(env_paths) do
  local f = io.open(p, "r")
  if f then
    f:close()
    env_vars = load_env(p)
    log("INFO", "Loaded .env from: " .. p)
    break
  end
end

local function get_env(key, default)
  return env_vars[key] or default
end

-- ── Configuration ─────────────────────────────────────────────
local PIPELINE_URL    = get_env("VOICEBOT_PIPELINE_URL", "http://127.0.0.1:8004/pipeline")
local PIPELINE_TIMEOUT = tonumber(get_env("VOICEBOT_PIPELINE_TIMEOUT", "30"))
local RECORD_MAX_SECS = tonumber(get_env("VOICEBOT_RECORD_MAX_SECS", "6"))
local RECORD_SIL_MS   = tonumber(get_env("VOICEBOT_RECORD_SIL_MS", "1000"))
local MAX_TURNS       = tonumber(get_env("VOICEBOT_MAX_TURNS", "8"))
local MIN_REC_BYTES   = 2000
local HELLO_TEXT      = get_env("VOICEBOT_HELLO_TEXT", "Hello! How can I help you today?")
local BYE_TEXT        = get_env("VOICEBOT_BYE_TEXT", "Thank you. Goodbye.")

-- ── TTS for hello/bye using TTS service directly ───────────────
local TTS_URL = get_env("TTS_URL", "http://127.0.0.1:8002")

local function speak_via_tts(session, text, wav_path)
  local cmd = string.format(
    [[curl -sS --max-time 15 -G "%s/synthesize" --data-urlencode "text=%s" --data-urlencode "format=wav" --data-urlencode "sample_rate=8000" -o %q]],
    TTS_URL, text, wav_path
  )
  local out, rc = shell(cmd)
  log("INFO", "TTS speak rc=" .. rc .. " size=" .. file_size(wav_path))
  if file_size(wav_path) > 2000 then
    session:execute("playback", wav_path)
  else
    log("ERR", "TTS output too small, skipping playback")
  end
  rm_file(wav_path)
end

-- ── Main pipeline call ─────────────────────────────────────────
local function call_pipeline(rec_wav, session_id, caller_id, response_wav)
  local cmd = string.format(
    [[curl -sS --max-time %d -X POST "%s" -F "audio=@%q" -F "session_id=%s" -F "caller_id=%s" -o %q -w "%%{http_code}"]],
    PIPELINE_TIMEOUT,
    PIPELINE_URL,
    rec_wav,
    session_id,
    caller_id,
    response_wav
  )
  log("INFO", "Pipeline call: " .. PIPELINE_URL)
  local out, rc = shell(cmd)
  local http_code = trim(out)
  log("INFO", "Pipeline http_code=" .. http_code .. " rc=" .. rc .. " response_size=" .. file_size(response_wav))
  return http_code == "200" and file_size(response_wav) > 2000
end

-- ── Call start ────────────────────────────────────────────────
session:answer()
session:sleep(300)

local uuid      = session:getVariable("uuid") or tostring(os.time())
local caller_id = session:getVariable("caller_id_number") or "unknown"

log("INFO", "Call started uuid=" .. uuid .. " caller=" .. caller_id)

-- Greet caller
local hello_wav = "/tmp/" .. uuid .. "_hello.wav"
speak_via_tts(session, HELLO_TEXT, hello_wav)

-- ── Conversation loop ─────────────────────────────────────────
for turn = 1, MAX_TURNS do
  if not session:ready() then
    log("INFO", "Session ended by caller at turn " .. turn)
    break
  end

  local rec_wav      = "/tmp/" .. uuid .. "_t" .. turn .. "_rec.wav"
  local response_wav = "/tmp/" .. uuid .. "_t" .. turn .. "_resp.wav"

  -- Record caller audio
  log("INFO", "Recording turn=" .. turn)
  session:execute("record", string.format(
    "%s %d %d", rec_wav, RECORD_MAX_SECS, RECORD_SIL_MS
  ))

  local rec_size = file_size(rec_wav)
  log("INFO", "Recorded " .. rec_size .. " bytes")

  if rec_size < MIN_REC_BYTES then
    log("ERR", "Audio too short, ending conversation")
    rm_file(rec_wav)
    break
  end

  -- Send to pipeline — single call handles STT + LLM + TTS
  local t_start = os.clock()
  local ok = call_pipeline(rec_wav, uuid, caller_id, response_wav)
  local elapsed = os.clock() - t_start
  log("INFO", string.format("Pipeline completed in %.2fs ok=%s", elapsed, tostring(ok)))

  rm_file(rec_wav)

  if not ok then
    log("ERR", "Pipeline failed at turn " .. turn)
    rm_file(response_wav)
    -- Play fallback message
    local fallback_wav = "/tmp/" .. uuid .. "_fallback.wav"
    speak_via_tts(session, "Sorry, I had trouble processing that. Please try again.", fallback_wav)
    goto continue
  end

  -- Play pipeline audio response
  session:execute("playback", response_wav)
  rm_file(response_wav)

  ::continue::
end

-- Goodbye
local bye_wav = "/tmp/" .. uuid .. "_bye.wav"
speak_via_tts(session, BYE_TEXT, bye_wav)

session:hangup()
log("INFO", "Call ended uuid=" .. uuid)
return
