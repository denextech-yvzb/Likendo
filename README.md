# Lidenko AI — Seva ya kuhost

Seva hii ni ya kujitegemea. Inashikilia Groq key yako, na app ya Lidenko POS inaiunganisha kwa URL na token tu.

## Hatua 1: Pata Groq key
1. Nenda https://console.groq.com/keys, ingia, kisha bonyeza **Create API Key**.
2. Nakili key (inaanza na `gsk_`). Usiitume popote isipokuwa kwenye hosting.

## Hatua 2: Tengeneza APP_TOKEN
Kwenye kompyuta, endesha:

    python3 -c "import secrets;print(secrets.token_urlsafe(32))"

Hii ndiyo **token** utakayoweka kwenye app. Ihifadhi.

## Hatua 3: Weka msimbo kwenye GitHub (repo PRIVATE)
Pakia folda hii yote, **bila** faili la `.env`. Faili la `.gitignore` tayari linalizuia.

## Hatua 4: Hosting kwenye Render (bure)
1. Nenda https://render.com, bonyeza **New > Web Service**, kisha uunganishe repo yako.
2. Weka mipangilio hii:
   - **Runtime:** Python 3
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 60`
3. Kwenye **Environment**, ongeza:

   | Jina | Thamani |
   |---|---|
   | `GROQ_API_KEY` | key yako ya Groq |
   | `APP_TOKEN` | token kutoka Hatua 2 |
   | `ALLOWED_ORIGINS` | `*` |
   | `PYTHON_VERSION` | `3.12.8` |

4. Bonyeza **Create Web Service** na usubiri hadi hali iwe **Live**. Render itakupa anwani kama `https://jina-lako.onrender.com`.

## Hatua 5: Thibitisha seva
Fungua `https://jina-lako.onrender.com/health` kwenye browser. Lazima uone:

    "configured": true

Ikiona `false`, kagua `GROQ_API_KEY` na `APP_TOKEN` kwenye Environment.

## Hatua 6: Weka kwenye app (baadaye)
Kwenye Lidenko POS, nenda **AI > Mipangilio ya seva**, kisha:
- **Anwani ya seva:** `https://jina-lako.onrender.com` (bila `/` mwishoni)
- **Token:** ile ya Hatua 2

Bonyeza **Hifadhi**, kisha **Jaribu muunganisho**. Ukiona "Imeunganishwa", AI iko tayari.

## Hosting nyingine
- **Railway:** New Project > Deploy from GitHub. `Procfile` inatumika kiotomatiki. Weka variables sawa na hapo juu.
- **Server yako (VPS):** `pip install -r requirements.txt`, kisha endesha ile Start Command. Weka HTTPS mbele yake (mfano nginx + certbot).

## Mambo ya kujua
- **Render ya bure hulala** baada ya dakika 15 bila maombi. Ombi la kwanza baada ya hapo linaweza kuchukua sekunde 30 hadi 60, na app inasubiri hadi sekunde 60. Ili kuepuka hilo, tumia huduma ya bure kama UptimeRobot kugonga `/health` kila dakika 5, au lipia plan ya kudumu.
- **Kubadilisha token:** badilisha `APP_TOKEN` kwenye hosting, kisha weka token mpya kwenye app.
- **Groq ikiondoa model:** badilisha `GROQ_MODEL` kwenye Environment. Model ya sasa ni `llama-3.3-70b-versatile`.
- **Faragha:** seva haihifadhi data ya biashara. Ujumbe na muhtasari unaotumwa wakati wa mazungumzo unapita Groq, kwa hiyo kagua sera ya faragha ya Groq.
- **Rate limit:** `RATE_LIMIT_PER_MIN` (chaguo-msingi 30 kwa dakika kwa kila mtumiaji).

## Jaribu kwenye kompyuta yako
    pip install -r requirements.txt
    cp .env.example .env        # kisha jaza GROQ_API_KEY na APP_TOKEN
    python3 app.py              # seva inaanza kwenye http://127.0.0.1:5000
    python3 test_server.py      # majaribio (hayahitaji Groq halisi)

## Njia za API
| Njia | Kazi | Token? |
|---|---|---|
| `GET /` | Hali ya huduma | Hapana |
| `GET /health` | Hali na usanidi (bila siri) | Hapana |
| `GET /api/tools` | Orodha ya zana zinazoruhusiwa | Ndiyo |
| `POST /api/chat` | Mazungumzo na zana | Ndiyo |
