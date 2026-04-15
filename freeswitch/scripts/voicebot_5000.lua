-- voicebot_5000.lua
-- FreeSWITCH Lua Voicebot: Record -> STT -> Agent -> TTS -> Playback
-- Direct playback, no sox conversion, optimised for latency.

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

local function safe_json_escape(s)
  s = tostring(s or "")
  s = s:gsub("\\", "\\\\")
  s = s:gsub('"', '\\"')
  s = s:gsub("\n", " ")
  s = s:gsub("\r", " ")
  return s
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

local function rm_files(...)
  local args = {...}
  for _, p in ipairs(args) do
    if p and p ~= "" then
      -- shell(string.format("rm -f %q", p))
    end
  end
end

local function lower(s)
  return string.lower(tostring(s or ""))
end

local function should_end(transcript)
  local t = lower(transcript)
  if t:find("bye", 1, true) then return true end
  if t:find("goodbye", 1, true) then return true end
  if t:find("thank you", 1, true) then return true end
  if t:find("thanks", 1, true) then return true end
  if t:find("stop", 1, true) then return true end
  return false
end

-- Config
local function load_env(filepath)
    local file = io.open(filepath, "r")
    if not file then
        freeswitch.consoleLog("ERR", "[voicebot] Could not open .env file: " .. filepath .. "\n")
        return {}
    end
    
    local env = {}
    for line in file:lines() do
        -- Ignore comments and empty lines
        line = line:match("^%s*(.-)%s*$") -- trim
        if line ~= "" and not line:match("^#") then
            local key, value = line:match("^([%w_]+)%s*=%s*(.+)$")
            if key and value then
                -- Remove quotes if present
                value = value:gsub("^['\"]", ""):gsub("['\"]$", "")
                env[key] = value
            end
        end
    end
    file:close()
    return env
end

-- Attempt to load .env from standard locations
local env_vars = {}
local env_paths = {
    "/etc/freeswitch/.env",          -- Docker/Linux standard
    "/usr/local/freeswitch/conf/.env",
    "./.env"                          -- Running from script dir
}

for _, p in ipairs(env_paths) do
    local f = io.open(p, "r")
    if f then
        f:close()
        env_vars = load_env(p)
        freeswitch.consoleLog("INFO", "[voicebot] Loaded .env from: " .. p .. "\n")
        break
    end
end

-- Helper to get env with fallback (keeps script running if .env missing)
local function get_env(key, default)
    return env_vars[key] or default
end

-- ==========================================
-- 2. CONFIGURATION (USING ENV VARS)
-- ==========================================
local BASE_URL = get_env("VOICEBOT_BASE_URL", "http://127.0.0.1")
local STT_PORT = get_env("VOICEBOT_STT_PORT", "8001")
local TTS_PORT = get_env("VOICEBOT_TTS_PORT", "8002")
local AGENT_PORT = get_env("VOICEBOT_AGENT_PORT", "8003")

local STT_URL   = BASE_URL .. ":" .. STT_PORT .. "/transcribe?sample_rate=16000&language=en"
local TTS_URL   = BASE_URL .. ":" .. TTS_PORT .. "/synthesize"
local AGENT_URL = BASE_URL .. ":" .. AGENT_PORT .. "/chat"

local HELLO_TEXT = "Hello! How can I help you today?"
local BYE_TEXT   = "Thank you. Goodbye."

local RECORD_MAX_SECS = 6
local RECORD_SIL_MS   = 1000          -- 1 second silence ends recording
local MIN_REC8_BYTES  = 2000
local MAX_TURNS = 8

local CURL_STT_MAX   = 40
local CURL_AGENT_MAX = 30
local CURL_TTS_MAX   = 25

local MAX_TTS_CHARS = 400             -- split long replies into chunks
local TTS_SPLIT_DELAY = 200

-- Split text into chunks at sentence boundaries
local function split_text_for_tts(text, max_len)
  local chunks = {}
  if #text <= max_len then
    table.insert(chunks, text)
    return chunks
  end
  local pattern = "([^.!?]+[.!?]%s*)"
  for sentence in text:gmatch(pattern) do
    if #sentence <= max_len then
      table.insert(chunks, sentence)
    else
      local start = 1
      while start <= #sentence do
        local last = start + max_len - 1
        if last >= #sentence then
          table.insert(chunks, sentence:sub(start))
          break
        end
        local space_pos = sentence:find("%s", start + max_len - 20, start + max_len, true)
        if space_pos then
          table.insert(chunks, sentence:sub(start, space_pos - 1))
          start = space_pos + 1
        else
          table.insert(chunks, sentence:sub(start, start + max_len - 1))
          start = start + max_len
        end
      end
    end
  end
  return chunks
end

-- Speak a text using TTS, playing each chunk directly
local function speak_text(session, text, uuid, turn)
  local chunks = split_text_for_tts(text, MAX_TTS_CHARS)
  for idx, chunk in ipairs(chunks) do
    local chunk_txt = "/tmp/" .. uuid .. "_t" .. turn .. "_chunk" .. idx .. ".txt"
    local chunk_wav = "/tmp/" .. uuid .. "_t" .. turn .. "_chunk" .. idx .. ".wav"

    local f = io.open(chunk_txt, "w")
    if f then f:write(chunk); f:close() end

    local tts_cmd = string.format(
      [[curl -sS --max-time %d -G "%s" --data-urlencode "text=%s" --data-urlencode "format=wav" --data-urlencode "sample_rate=8000" --data-urlencode "length_scale=1.0" --data-urlencode "noise_scale=0.3" --data-urlencode "noise_w=0.6" -o %q]],
      CURL_TTS_MAX, TTS_URL, chunk, chunk_wav
    )
    log("INFO", "TTS command: " .. tts_cmd)
    local out, rc = shell(tts_cmd)
    log("INFO", "TTS curl exit code: " .. rc .. ", output: " .. out)
    local sz = file_size(chunk_wav)
    log("INFO", "TTS output file size: " .. sz)
    if sz < 2000 then
      log("ERR", "TTS chunk too small, skipping")
      goto skip
    end

    session:execute("playback", chunk_wav)
    session:sleep(TTS_SPLIT_DELAY)

    ::skip::
    rm_files(chunk_txt, chunk_wav)
  end
end

-- Call init
session:answer()
session:sleep(200)

local uuid = session:getVariable("uuid") or tostring(os.time())
local conversation_id = nil

speak_text(session, HELLO_TEXT, uuid, 0)

-- Main loop
for turn = 1, MAX_TURNS do
  if not session:ready() then break end

  local rec8        = "/tmp/" .. uuid .. "_t" .. turn .. ".wav"
  local rec16       = "/tmp/" .. uuid .. "_t" .. turn .. "_16k.wav"
  local reply_txt   = "/tmp/" .. uuid .. "_t" .. turn .. "_reply.txt"
  local tts_raw_wav = "/tmp/" .. uuid .. "_t" .. turn .. "_tts.wav"
  local reply_wav8k = "/tmp/" .. uuid .. "_t" .. turn .. "_reply_8k.wav"

  session:execute("record", string.format("%s %d %d", rec8, RECORD_MAX_SECS, RECORD_SIL_MS))
  local rec8_sz = file_size(rec8)
  log("INFO", string.format("turn=%d rec8=%s size=%d", turn, rec8, rec8_sz))

  if rec8_sz < MIN_REC8_BYTES then
    log("ERR", "No/low audio. Ending conversation.")
    rm_files(rec8, rec16, reply_txt, tts_raw_wav, reply_wav8k)
    break
  end

  shell(string.format("sox %q -r 16000 -c 1 -b 16 %q", rec8, rec16))
  if file_size(rec16) < 4000 then
    log("ERR", "rec16 too small after resample.")
    rm_files(rec8, rec16, reply_txt, tts_raw_wav, reply_wav8k)
    break
  end

  log("INFO", "Calling STT: " .. STT_URL)
  local stt_cmd = string.format(
    [[curl -sS --max-time %d -X POST "%s" -F "file=@%s" -w " HTTP_CODE:%%{http_code}\n"]],
    CURL_STT_MAX, STT_URL, rec16
  )
  local stt_resp, _ = shell(stt_cmd)
  log("INFO", "stt_resp=" .. (stt_resp:gsub("\n", " "):sub(1, 800)))

  local stt_extract = string.format([[
python3 - <<'PY'
import json
s=%s
s=s.strip()
try:
    obj, idx = json.JSONDecoder().raw_decode(s)
    print((obj.get("text","") or "").strip())
except Exception:
    print("")
PY
]], string.format("%q", stt_resp))

  local transcript, _ = shell(stt_extract)
  transcript = trim(transcript)
  log("INFO", "transcript=" .. transcript)

  if transcript == "" then
    log("ERR", "Empty transcript. Ending conversation.")
    rm_files(rec8, rec16, reply_txt, tts_raw_wav, reply_wav8k)
    break
  end

  if should_end(transcript) then
    log("INFO", "User requested end.")
    rm_files(rec8, rec16, reply_txt, tts_raw_wav, reply_wav8k)
    break
  end

  local cid_json = (conversation_id == nil) and "null" or ('"' .. safe_json_escape(conversation_id) .. '"')
  local agent_payload = string.format('{"text":"%s","conversation_id":%s}', safe_json_escape(transcript), cid_json)

  local agent_payload_file = "/tmp/" .. uuid .. "_t" .. turn .. "_agent_payload.json"
  do
    local f = io.open(agent_payload_file, "w")
    if f then f:write(agent_payload) f:close() end
  end

  local agent_cmd = string.format(
    [[curl -sS --max-time %d -X POST "%s" -H "Content-Type: application/json" --data-binary @%q -w " HTTP_CODE:%%{http_code}\n"]],
    CURL_AGENT_MAX, AGENT_URL, agent_payload_file
  )
  local agent_resp, _ = shell(agent_cmd)
  log("INFO", "agent_resp=" .. (agent_resp:gsub("\n", " "):sub(1, 800)))

  local agent_extract = string.format([[
python3 - <<'PY'
import json
s=%s
s=s.strip()
try:
    obj, idx = json.JSONDecoder().raw_decode(s)
    resp = (obj.get("response","") or "").strip()
    cid  = obj.get("conversation_id", None)
    print(resp)
    print("" if cid is None else str(cid))
except Exception:
    print("")
    print("")
PY
]], string.format("%q", agent_resp))

  local agent_out, _ = shell(agent_extract)
  local resp_line = agent_out:match("([^\n]*)") or ""
  local cid_line  = agent_out:match("\n([^\n]*)") or ""
  local reply_text = trim(resp_line)
  cid_line = trim(cid_line)

  if cid_line ~= "" then conversation_id = cid_line end
  if reply_text == "" then reply_text = "Sorry, I could not generate a response." end
  log("INFO", "reply_text=" .. reply_text .. " conversation_id=" .. tostring(conversation_id))

  rm_files(agent_payload_file)

  speak_text(session, reply_text, uuid, turn)

  rm_files(rec8, rec16, reply_txt, tts_raw_wav, reply_wav8k)
end

speak_text(session, BYE_TEXT, uuid, "bye")
session:hangup()
return
