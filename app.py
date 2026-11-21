"""
Lidenko AI — seva ya kujitegemea (standalone)

Seva hii inakaa kwenye hosting yake yenyewe, tofauti na Lidenko POS.
  * GROQ_API_KEY inakaa kwenye seva hii tu. Haiwekwi kwenye app, APK wala browser.
  * Kila ombi linahitaji APP_TOKEN (Bearer token) na lina rate limit.
  * Zana (tools) zimeorodheshwa kwenye lidenko_tools.py. Kila ombi la zana linakaguliwa.
  * Seva haihifadhi data ya biashara. Ujumbe unapita Groq tu wakati wa mazungumzo.
"""
import hashlib
import hmac
import json
import logging
import os
import re
import threading
import time
from collections import defaultdict, deque

import requests
from flask import Flask, jsonify, make_response, request

import lidenko_tools as nt


def _load_dotenv(path):
    """Soma faili la .env (hiari). Environment Variables za hosting zina nguvu zaidi."""
    if not os.path.isfile(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))


def cfg(name, default=""):
    return os.environ.get(name, default)


GROQ_BASE_URL = cfg("GROQ_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/")
GROQ_MODEL = cfg("GROQ_MODEL", "llama-3.3-70b-versatile")
RATE_LIMIT_PER_MIN = int(cfg("RATE_LIMIT_PER_MIN", "30"))
GROQ_TIMEOUT = float(cfg("GROQ_TIMEOUT", "45"))
MAX_MESSAGES = 40
MAX_TEXT = 8000
MAX_TOOL_TEXT = 20000
MAX_TOOL_CALLS = 6

_origins = [o.strip() for o in cfg("ALLOWED_ORIGINS", "*").split(",") if o.strip()]
ALLOW_ALL = "*" in _origins

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("lidenko-ai")

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 512 * 1024  # 512KB

BASE_SYSTEM = """Wewe ni Lidenko AI, msaidizi wa biashara ndani ya Lidenko POS. Unamsaidia mmiliki wa duka kuelewa na kusimamia biashara yake.

KANUNI ZISIZOVUNJIKA:
1. Takwimu zote (mauzo, faida, matumizi, stock, bei, madeni, bills, kodi) lazima zitoke kwenye zana. Usibuni namba. Usifanye hesabu za fedha mwenyewe: nakili namba zilizotolewa na zana. Zana ikileta kosa au data haipo, sema hivyo wazi.
2. Tofautisha 'ukweli' (kutoka data) na 'ushauri' (maoni yako). Ushauri uungwe mkono na namba ulizopata.
3. Mabadiliko ya data (matumizi, stock, kikumbusho, backup) yafanywe kwa zana husika tu. Mfumo utamwomba mtumiaji athibitishe. Usiseme kitendo kimefanikiwa mpaka matokeo ya zana yasema hivyo. Mtumiaji akikataa, kubali.
4. Huna ruhusa ya kufuta data, kubadilisha bei, kurekodi mauzo, kulipa madeni au kurejesha backup. Mtumiaji akiomba, mwelekeze kwenye ukurasa husika kwa navigate_to.
5. Linda faragha ya wateja. Usitaje namba za simu.
6. Usimshutumu mtu yeyote kwa wizi au udanganyifu. Unaweza kusema 'kuna mabadiliko yasiyo ya kawaida yanayostahili kukaguliwa'.
7. Utabiri na makadirio yataje kuwa si uhakika.
8. Majibu mafupi, yanayosomeka kwenye simu. Usirudie swali la mtumiaji.
9. Mtumiaji akiomba kufungua ukurasa (mfano 'fungua mauzo'), tumia navigate_to.
10. Lugha ya jibu ni ile iliyo kwenye MUKTADHA. Usichanganye lugha mbili kwenye jibu moja.
11. Tumia emoji zisizozidi moja kwa jibu, au hakuna kabisa."""


# ---------------------------------------------------------------- helpers
def _json_error(message, status, **extra):
    body = {"error": message}
    body.update(extra)
    return jsonify(body), status


@app.after_request
def common_headers(resp):
    origin = request.headers.get("Origin")
    if origin and (ALLOW_ALL or origin in _origins):
        resp.headers["Access-Control-Allow-Origin"] = "*" if ALLOW_ALL else origin
        resp.headers["Vary"] = "Origin"
        resp.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
        resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        resp.headers["Access-Control-Max-Age"] = "600"
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Cache-Control"] = "no-store"
    return resp


_hits = defaultdict(deque)
_hits_lock = threading.Lock()


def rate_limited(client_id):
    """Rudisha sekunde za kusubiri, au 0 kama ombi linaruhusiwa."""
    now = time.time()
    with _hits_lock:
        q = _hits[client_id]
        while q and now - q[0] > 60:
            q.popleft()
        if len(q) >= RATE_LIMIT_PER_MIN:
            return int(60 - (now - q[0])) + 1
        q.append(now)
    return 0


def auth_error():
    """Rudisha None kama ombi limeidhinishwa, au jibu la kosa."""
    token = cfg("APP_TOKEN")
    if len(token) < 16:
        return _json_error("Server haijawekwa vizuri: APP_TOKEN ni fupi au haipo.", 503)
    header = request.headers.get("Authorization", "")
    supplied = header[7:].strip() if header.lower().startswith("bearer ") else ""
    if not supplied or not hmac.compare_digest(supplied.encode(), token.encode()):
        return _json_error("Token si sahihi.", 401)
    cid = hashlib.sha256((token + (request.remote_addr or "")).encode()).hexdigest()[:16]
    wait = rate_limited(cid)
    if wait:
        resp, code = _json_error("Maombi mengi mno. Subiri kidogo.", 429, retry_after=wait)
        resp.headers["Retry-After"] = str(wait)
        return resp, code
    return None


def _clip(text, limit):
    text = text if isinstance(text, str) else ""
    return text if len(text) <= limit else text[:limit] + "\n...[imekatwa]"


def sanitize_messages(raw):
    """Jenga upya mazungumzo kwa vitu vinavyoruhusiwa tu. Rudisha (messages, error)."""
    if not isinstance(raw, list) or not raw:
        return None, "messages zinahitajika"
    raw = raw[-MAX_MESSAGES:]
    out = []
    for m in raw:
        if not isinstance(m, dict):
            return None, "message si sahihi"
        role = m.get("role")
        if role == "user":
            out.append({"role": "user", "content": _clip(m.get("content"), MAX_TEXT)})
        elif role == "assistant":
            msg = {"role": "assistant", "content": _clip(m.get("content"), MAX_TEXT) or None}
            calls = m.get("tool_calls")
            if calls:
                if not isinstance(calls, list) or len(calls) > MAX_TOOL_CALLS:
                    return None, "tool_calls si sahihi"
                clean_calls = []
                for c in calls:
                    fn = (c or {}).get("function") or {}
                    name, cid = fn.get("name"), (c or {}).get("id")
                    if name not in nt.TOOLS or not isinstance(cid, str) or not re.fullmatch(r"[\w\-]{1,64}", cid):
                        return None, "tool_call si sahihi"
                    args = fn.get("arguments")
                    args = args if isinstance(args, str) else json.dumps(args or {})
                    clean_calls.append({"id": cid, "type": "function",
                                        "function": {"name": name, "arguments": _clip(args, 2000)}})
                msg["tool_calls"] = clean_calls
            out.append(msg)
        elif role == "tool":
            cid = m.get("tool_call_id")
            if not isinstance(cid, str) or not re.fullmatch(r"[\w\-]{1,64}", cid):
                return None, "tool_call_id si sahihi"
            out.append({"role": "tool", "tool_call_id": cid, "content": _clip(m.get("content"), MAX_TOOL_TEXT)})
        else:
            return None, "role si sahihi"
    # Mazungumzo hayaanzi na tool au assistant mwenye tool_calls (Groq ingekataa)
    while out and (out[0]["role"] == "tool" or (out[0]["role"] == "assistant" and out[0].get("tool_calls"))):
        out.pop(0)
    if not out or out[-1]["role"] not in ("user", "tool"):
        return None, "ujumbe wa mwisho lazima uwe wa mtumiaji au matokeo ya zana"
    return out, None


def build_system(context):
    context = context if isinstance(context, dict) else {}
    lines = []
    for key, label in (("store", "Duka"), ("now", "Tarehe na saa ya sasa"), ("timezone", "Saa za"), ("currency", "Sarafu")):
        value = context.get(key)
        if isinstance(value, str) and value.strip():
            clean = re.sub(r"[\r\n]+", " ", value.strip())
            lines.append("- " + label + ": " + _clip(clean, 80))
    if context.get("lang") == "en":
        lines.append("- Answer language: English only.")
    else:
        lines.append("- Lugha ya jibu: Kiswahili pekee.")
    return BASE_SYSTEM + "\n\nMUKTADHA:\n" + "\n".join(lines)


def call_groq(messages):
    key = cfg("GROQ_API_KEY")
    if not key:
        return None, _json_error("Server haijawekwa vizuri: GROQ_API_KEY haipo.", 503)
    payload = {"model": GROQ_MODEL, "messages": messages, "tools": nt.openai_tools(),
               "tool_choice": "auto", "temperature": 0.3, "max_tokens": 1024}
    last = None
    for attempt in range(2):  # jaribu mara moja zaidi kwa makosa ya muda
        try:
            r = requests.post(f"{GROQ_BASE_URL}/chat/completions", json=payload, timeout=GROQ_TIMEOUT,
                              headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
        except requests.Timeout:
            last = _json_error("AI imechelewa kujibu. Jaribu tena.", 504)
            continue
        except requests.RequestException:
            last = _json_error("Server imeshindwa kufikia Groq.", 502)
            continue
        if r.status_code == 200:
            try:
                return r.json(), None
            except ValueError:
                last = _json_error("Jibu la Groq si sahihi.", 502)
                continue
        if r.status_code == 429:
            return None, _json_error("Groq inaombwa maombi mengi. Subiri kidogo.", 429)
        if r.status_code == 400 and "tool_use_failed" in r.text and attempt == 0:
            payload["temperature"] = 0  # Llama wakati mwingine huvunja muundo wa tool call
            last = _json_error("AI imeshindwa kuandaa ombi la zana. Jaribu tena.", 502)
            continue
        if r.status_code in (401, 403):
            log.error("Groq imekataa key (status %s). Angalia GROQ_API_KEY.", r.status_code)
            return None, _json_error("Server haijawekwa vizuri: Groq imekataa key.", 502)
        if r.status_code >= 500:
            last = _json_error("Groq ina tatizo la muda. Jaribu tena.", 502)
            continue
        log.warning("Groq status %s", r.status_code)
        return None, _json_error("Ombi limekataliwa na Groq.", 502)
    return None, last or _json_error("Imeshindikana.", 502)


# ---------------------------------------------------------------- routes
@app.route("/")
def index():
    return jsonify({"service": "lidenko-ai", "status": "ok", "health": "/health"})


@app.route("/health")
def health():
    return jsonify({"status": "ok", "service": "lidenko-ai", "model": GROQ_MODEL,
                    "configured": bool(cfg("GROQ_API_KEY")) and len(cfg("APP_TOKEN")) >= 16})


@app.route("/api/tools", methods=["GET", "OPTIONS"])
def tools():
    if request.method == "OPTIONS":
        return make_response("", 204)
    denied = auth_error()
    if denied:
        return denied
    return jsonify({"tools": [{"name": n, "sensitive": t["sensitive"]} for n, t in nt.TOOLS.items()]})


@app.route("/api/chat", methods=["POST", "OPTIONS"])
def chat():
    if request.method == "OPTIONS":
        return make_response("", 204)
    denied = auth_error()
    if denied:
        return denied
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return _json_error("JSON si sahihi.", 400)
    msgs, bad = sanitize_messages(data.get("messages"))
    if bad:
        return _json_error(bad, 400)
    groq_msgs = [{"role": "system", "content": build_system(data.get("context"))}] + msgs
    result, err = call_groq(groq_msgs)
    if err:
        return err
    try:
        choice = result["choices"][0]["message"]
    except (KeyError, IndexError, TypeError):
        return _json_error("Jibu la Groq si sahihi.", 502)

    out_calls, rejected = [], []
    for c in (choice.get("tool_calls") or [])[:MAX_TOOL_CALLS]:
        fn = c.get("function") or {}
        name = fn.get("name")
        try:
            args = json.loads(fn.get("arguments") or "{}")
        except ValueError:
            rejected.append({"name": name, "reason": "vigezo si JSON"})
            continue
        clean, why = nt.validate_args(name, args)
        if why:
            rejected.append({"name": name, "reason": why})
            continue
        out_calls.append({"id": c.get("id") or f"call_{len(out_calls)}", "type": "function",
                          "function": {"name": name, "arguments": json.dumps(clean, ensure_ascii=False)},
                          "requires_confirmation": nt.is_sensitive(name)})
    content = choice.get("content")
    if rejected and not out_calls and not content:
        log.info("Ombi la zana limekataliwa: %d", len(rejected))
        content = "Samahani, sikuweza kuandaa ombi hilo kwa usahihi. Tafadhali jaribu kuliandika tena."
    message = {"role": "assistant", "content": content}
    if out_calls:
        message["tool_calls"] = out_calls
    log.info("chat ok msgs=%d calls=%d rejected=%d", len(msgs), len(out_calls), len(rejected))
    return jsonify({"message": message, "rejected": rejected, "model": result.get("model", GROQ_MODEL),
                    "usage": result.get("usage", {})})


@app.errorhandler(404)
def not_found(_):
    return _json_error("Haipatikani.", 404)


@app.errorhandler(413)
def too_big(_):
    return _json_error("Ombi ni kubwa mno.", 413)


@app.errorhandler(500)
def server_error(_):
    return _json_error("Hitilafu ya server.", 500)


if __name__ == "__main__":
    app.run(host=cfg("HOST", "0.0.0.0"), port=int(cfg("PORT", "5000")), debug=False)
