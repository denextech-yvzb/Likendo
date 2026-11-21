"""
Lidenko AI — Orodha ya zana (tools) zinazoruhusiwa.

Hii ndiyo "chanzo kimoja cha ukweli" cha kile AI inaruhusiwa kuomba.
- Backend inatuma schemas hizi kwa Groq (function calling).
- Backend inakagua kila ombi la AI (jina + vigezo) kabla ya kulituma kwa app.
- App (ai.js) inakagua tena na kutekeleza kwenye data ya duka (localStorage).
Hakuna zana ya kufuta data, kubadilisha bei, kurekodi mauzo au kurejesha backup.
"""
from datetime import datetime

PAGES = ["dashboard", "products", "reminders", "notes", "personaldebts", "sales", "stock",
         "suppliers", "purchases", "expenses", "bills", "debts", "returns", "reports",
         "advice", "calculator", "settings", "backup", "help", "ai"]
PERIODS = ["today", "yesterday", "week", "month", "year", "all"]
PERIOD_DESC = ("Kipindi: today=leo, yesterday=jana, week=siku 7 zilizopita (pamoja na leo), "
               "month=mwezi huu hadi leo, year=mwaka huu hadi leo, all=tangu mwanzo.")


def P(type_, desc, **kw):
    d = {"type": type_, "description": desc}
    d.update(kw)
    return d


TOOLS = {
    # ---------------- ZANA ZA KUSOMA (hazibadilishi data) ----------------
    "get_business_summary": dict(
        desc="Muhtasari wa fedha wa kipindi: mauzo, returns, COGS, faida ghafi, matumizi, faida halisi (zimehesabiwa na mfumo).",
        params={"period": P("string", PERIOD_DESC, enum=PERIODS)}, required=["period"], sensitive=False),
    "compare_periods": dict(
        desc="Linganisha kipindi cha sasa na kilichotangulia (mauzo, matumizi, faida) na asilimia ya mabadiliko.",
        params={"period": P("string", "week (siku 7 vs siku 7 zilizotangulia) au month (mwezi huu hadi leo vs mwezi uliopita kamili).", enum=["week", "month"])},
        required=["period"], sensitive=False),
    "get_top_products": dict(
        desc="Bidhaa zinazouzika zaidi au kidogo zaidi kwa kipindi.",
        params={"period": P("string", PERIOD_DESC, enum=PERIODS),
                "metric": P("string", "qty=idadi, revenue=mapato, profit=faida.", enum=["qty", "revenue", "profit"]),
                "order": P("string", "best=zinazoongoza, worst=zinazouzika polepole.", enum=["best", "worst"]),
                "limit": P("integer", "Idadi ya bidhaa (1-20). Default 5.", minimum=1, maximum=20)},
        required=["period"], sensitive=False),
    "search_products": dict(
        desc="Tafuta bidhaa kwa jina au code; inarudisha bei halisi na stock iliyopo.",
        params={"query": P("string", "Jina au code ya bidhaa.", maxLength=80)}, required=["query"], sensitive=False),
    "get_stock_status": dict(
        desc="Hali ya stock: bidhaa zilizoisha, zenye stock ndogo, na thamani ya stock.",
        params={}, required=[], sensitive=False),
    "get_sales": dict(
        desc="Orodha ya mauzo ya hivi karibuni ya kipindi (hiari: chuja kwa bidhaa).",
        params={"period": P("string", PERIOD_DESC, enum=PERIODS),
                "product": P("string", "Jina la bidhaa la kuchuja (hiari).", maxLength=80),
                "limit": P("integer", "Idadi ya mauzo (1-50). Default 10.", minimum=1, maximum=50)},
        required=["period"], sensitive=False),
    "get_expenses": dict(
        desc="Matumizi ya kipindi, jumla kwa kila category, na matumizi makubwa zaidi.",
        params={"period": P("string", PERIOD_DESC, enum=PERIODS),
                "category": P("string", "Chuja kwa category (hiari).", maxLength=40)},
        required=["period"], sensitive=False),
    "get_debts": dict(
        desc="Madeni ya wateja ambayo hayajalipwa kikamilifu (majina na baki; bila namba za simu).",
        params={}, required=[], sensitive=False),
    "get_personal_debts": dict(
        desc="Madeni binafsi ya mmiliki (ya kukopa / kukopesha) yaliyorekodiwa.",
        params={}, required=[], sensitive=False),
    "get_bills": dict(
        desc="Bills (zilizolipwa / zisizolipwa).",
        params={"status": P("string", "unpaid, paid au all.", enum=["unpaid", "paid", "all"])},
        required=[], sensitive=False),
    "get_purchases": dict(
        desc="Oda za bidhaa kutoka kwa suppliers (zinazosubiri au zilizopokelewa).",
        params={"status": P("string", "pending, received au all.", enum=["pending", "received", "all"])},
        required=[], sensitive=False),
    "get_suppliers": dict(
        desc="Orodha ya suppliers na jumla ya oda zilizopokelewa kutoka kwa kila mmoja.",
        params={}, required=[], sensitive=False),
    "get_returns": dict(
        desc="Bidhaa zilizorudishwa na wateja kwa kipindi.",
        params={"period": P("string", PERIOD_DESC, enum=PERIODS)}, required=["period"], sensitive=False),
    "get_recent_activity": dict(
        desc="Shughuli za hivi karibuni zilizorekodiwa kwenye mfumo (activity log).",
        params={"limit": P("integer", "Idadi (1-50). Default 15.", minimum=1, maximum=50)},
        required=[], sensitive=False),
    "get_backup_status": dict(
        desc="Hali ya backup: lini ilifanywa mara ya mwisho na kama imechelewa.",
        params={}, required=[], sensitive=False),
    "get_reminders": dict(
        desc="Vikumbusho vya biashara (vinavyosubiri / vilivyokamilika).",
        params={"status": P("string", "pending, done au all.", enum=["pending", "done", "all"])},
        required=[], sensitive=False),

    "get_tax_summary": dict(
        desc="Makadirio ya kodi kwa kipindi: VAT (kwa biashara iliyosajiliwa) au turnover tax (kwa asiye na VAT), kulingana na mipangilio ya duka.",
        params={"period": P("string", PERIOD_DESC, enum=PERIODS)}, required=["period"], sensitive=False),

    # ---------------- NAVIGATION (haibadilishi data) ----------------
    "navigate_to": dict(
        desc="Fungua ukurasa wa Lidenko POS. Mfano: 'fungua mauzo' => sales, 'madeni' => debts, 'bidhaa' => products.",
        params={"page": P("string", "Kitambulisho cha ukurasa.", enum=PAGES)}, required=["page"], sensitive=False),

    # ---------------- ZANA ZINAZOBADILISHA DATA (zinahitaji uthibitisho wa mtumiaji) ----------------
    "add_expense": dict(
        desc="Rekodi matumizi mapya ya biashara. Mtumiaji ataombwa kuthibitisha kabla ya kuhifadhiwa.",
        params={"name": P("string", "Jina la matumizi.", maxLength=80),
                "amount": P("number", "Kiasi cha fedha (TZS), zaidi ya 0.", minimum=0.01, maximum=1000000000),
                "category": P("string", "Category (mfano Usafiri, Kodi, Umeme, Maji, Mishahara, Matengenezo, Nyingine).", maxLength=40),
                "notes": P("string", "Maelezo (hiari).", maxLength=200)},
        required=["name", "amount"], sensitive=True),
    "add_stock": dict(
        desc="Ongeza stock ya bidhaa iliyopo. Mtumiaji ataombwa kuthibitisha.",
        params={"product": P("string", "Jina la bidhaa (lazima ilingane na bidhaa moja iliyopo).", maxLength=80),
                "quantity": P("number", "Idadi ya kuongeza, zaidi ya 0.", minimum=0.01, maximum=1000000)},
        required=["product", "quantity"], sensitive=True),
    "create_reminder": dict(
        desc="Weka kikumbusho cha biashara. Mtumiaji ataombwa kuthibitisha.",
        params={"title": P("string", "Kichwa cha kikumbusho.", maxLength=120),
                "datetime": P("string", "Tarehe na muda wa saa za mtumiaji, muundo YYYY-MM-DDTHH:MM.", maxLength=16)},
        required=["title", "datetime"], sensitive=True),
    "create_backup": dict(
        desc="Pakua backup kamili ya data ya duka (faili la JSON). Mtumiaji ataombwa kuthibitisha.",
        params={}, required=[], sensitive=True),
}


def openai_tools():
    """Schemas kwa muundo wa Groq/OpenAI function calling."""
    out = []
    for name, t in TOOLS.items():
        out.append({"type": "function", "function": {
            "name": name, "description": t["desc"],
            "parameters": {"type": "object", "properties": t["params"], "required": t["required"],
                           "additionalProperties": False}}})
    return out


def is_sensitive(name):
    return bool(TOOLS.get(name, {}).get("sensitive"))


def validate_args(name, args):
    """Rudisha (cleaned_args, error). Inakataa vigezo visivyojulikana na aina/ukubwa usio sahihi."""
    spec = TOOLS.get(name)
    if spec is None:
        return None, f"Zana '{name}' haiko kwenye orodha inayoruhusiwa"
    if args is None:
        args = {}
    if not isinstance(args, dict):
        return None, "Vigezo vinapaswa kuwa object"
    unknown = set(args) - set(spec["params"])
    if unknown:
        return None, "Vigezo visivyoruhusiwa: " + ", ".join(sorted(unknown))
    clean = {}
    for key, rule in spec["params"].items():
        if key not in args or args[key] is None or args[key] == "":
            if key in spec["required"]:
                return None, f"Kigezo '{key}' kinahitajika"
            continue
        v = args[key]
        t = rule["type"]
        if t == "string":
            if not isinstance(v, str):
                return None, f"'{key}' lazima iwe maandishi"
            v = v.strip()
            if len(v) > rule.get("maxLength", 200):
                return None, f"'{key}' ni refu mno"
            if "enum" in rule and v not in rule["enum"]:
                return None, f"'{key}' si sahihi"
        elif t in ("number", "integer"):
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                return None, f"'{key}' lazima iwe namba"
            if v != v or v in (float("inf"), float("-inf")):
                return None, f"'{key}' si sahihi"
            if t == "integer":
                if int(v) != v:
                    return None, f"'{key}' lazima iwe namba kamili"
                v = int(v)
            if "minimum" in rule and v < rule["minimum"]:
                return None, f"'{key}' ni ndogo mno"
            if "maximum" in rule and v > rule["maximum"]:
                return None, f"'{key}' ni kubwa mno"
        clean[key] = v
    if name == "create_reminder":
        try:
            datetime.strptime(clean["datetime"], "%Y-%m-%dT%H:%M")
        except ValueError:
            return None, "datetime lazima iwe YYYY-MM-DDTHH:MM"
    return clean, None
