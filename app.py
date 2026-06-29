from flask import Flask, render_template, request, jsonify, session, redirect, url_for, make_response
from functools import wraps
from dotenv import load_dotenv
from pathlib import Path
import os, json, sqlite3, uuid
from datetime import datetime

load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")

app = Flask(__name__)
app.secret_key = "luxury-chatbot-secret-2024"

from groq import Groq
client = Groq(api_key=os.environ.get("GROQ_API_KEY", ""))

# ─────────────────────────────────────────────
#  Multilingual prompts
# ─────────────────────────────────────────────
SYSTEM_PROMPTS = {
    "fr": """Tu es Lumia, une assistante IA premium et élégante.
RÈGLES ABSOLUES :
- Réponds TOUJOURS en 1 à 3 phrases maximum. Jamais plus.
- Sois directe, chaleureuse, raffinée.
- Pas de listes, pas de bullet points, pas de titres.
- Si la question nécessite plus, propose de développer.
- Adapte ton ton à l'humeur de l'utilisateur.
- Langue : français uniquement.""",

    "en": """You are Lumia, a premium and elegant AI assistant.
ABSOLUTE RULES:
- ALWAYS reply in 1 to 3 sentences maximum. Never more.
- Be direct, warm, and refined.
- No lists, no bullet points, no titles.
- Adapt your tone to the user's mood.
- Language: English only.""",

    "ar": """أنتِ لوميا، مساعدة ذكاء اصطناعي متميزة وأنيقة.
القواعد المطلقة:
- أجيبي دائماً في جملة إلى ثلاث جمل كحد أقصى.
- كوني مباشرة، دافئة، وراقية.
- لا قوائم، لا نقاط، لا عناوين.
- اللغة: العربية فقط."""
}

SENTIMENT_PROMPTS = {
    "fr": 'Analyse le sentiment. Réponds UNIQUEMENT avec ce JSON: {"label":"positif","score":0.8,"percentage":80}',
    "en": 'Analyze sentiment. Reply ONLY with: {"label":"positif","score":0.8,"percentage":80}',
    "ar": 'حلل المشاعر. أجب فقط بـ: {"label":"positif","score":0.8,"percentage":80}'
}

WHISPER_LANG  = {"fr": "fr", "en": "en", "ar": "ar"}
TTS_LANG      = {"fr": "fr-FR", "en": "en-US", "ar": "ar-SA"}
WELCOME_MSG   = {
    "fr": "Bonjour, je suis Lumia. Comment puis-je vous aider aujourd'hui ?",
    "en": "Hello, I'm Lumia. How can I help you today?",
    "ar": "مرحباً، أنا لوميا. كيف يمكنني مساعدتك اليوم؟"
}

LOCAL_REPLIES = {
    "fr": {
        "hello":    "Bonjour ! Comment puis-je vous aider aujourd'hui ?",
        "thanks":   "Avec plaisir, c'est un honneur de vous assister !",
        "hours":    "Nous sommes disponibles du lundi au vendredi de 9h à 19h, samedi de 10h à 16h.",
        "contact":  "Contactez-nous à support@exemple.com ou au 01 23 45 67 89.",
        "password": "Cliquez sur 'Mot de passe oublié' sur la page de connexion.",
        "default":  "Je vous comprends. Pouvez-vous me donner plus de détails ?"
    },
    "en": {
        "hello":    "Hello! How can I help you today?",
        "thanks":   "My pleasure, it's an honour to assist you!",
        "hours":    "We're available Monday to Friday 9am–7pm, Saturday 10am–4pm.",
        "contact":  "Reach us at support@example.com or call +1-800-123-4567.",
        "password": "Click 'Forgot password' on the login page to reset it.",
        "default":  "I understand. Could you give me a bit more detail?"
    },
    "ar": {
        "hello":    "مرحباً! كيف يمكنني مساعدتك اليوم؟",
        "thanks":   "بكل سرور، يسعدني مساعدتك!",
        "hours":    "نحن متاحون من الاثنين إلى الجمعة من 9 صباحاً حتى 7 مساءً.",
        "contact":  "تواصل معنا على support@example.com أو على الرقم 0123456789.",
        "password": "انقر على 'نسيت كلمة المرور' في صفحة تسجيل الدخول.",
        "default":  "أفهمك. هل يمكنك إعطائي مزيداً من التفاصيل؟"
    }
}

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"


# ─────────────────────────────────────────────
#  Auth decorator
# ─────────────────────────────────────────────
def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("admin"):
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return decorated


# ─────────────────────────────────────────────
#  Database
# ─────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect("chatbot.db")
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id     TEXT,
            role           TEXT,
            message        TEXT,
            sentiment_score  REAL,
            sentiment_label  TEXT,
            language       TEXT DEFAULT 'fr',
            created_at     TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sessions_info (
            session_id    TEXT PRIMARY KEY,
            first_seen    TEXT,
            last_seen     TEXT,
            message_count INTEGER DEFAULT 0,
            language      TEXT DEFAULT 'fr'
        )
    """)
    for col in ["language"]:
        try:
            conn.execute(f"ALTER TABLE conversations ADD COLUMN {col} TEXT DEFAULT 'fr'")
        except Exception:
            pass
        try:
            conn.execute(f"ALTER TABLE sessions_info ADD COLUMN {col} TEXT DEFAULT 'fr'")
        except Exception:
            pass
    conn.commit()
    conn.close()


def save_message(session_id, role, message,
                 sentiment_score=None, sentiment_label=None, language="fr"):
    conn = get_db()
    conn.execute(
        "INSERT INTO conversations "
        "(session_id,role,message,sentiment_score,sentiment_label,language,created_at) "
        "VALUES (?,?,?,?,?,?,?)",
        (session_id, role, message, sentiment_score,
         sentiment_label, language, datetime.now().isoformat())
    )
    now = datetime.now().isoformat()
    conn.execute("""
        INSERT INTO sessions_info (session_id,first_seen,last_seen,message_count,language)
        VALUES (?,?,?,1,?)
        ON CONFLICT(session_id) DO UPDATE SET
            last_seen=excluded.last_seen,
            message_count=message_count+1,
            language=excluded.language
    """, (session_id, now, now, language))
    conn.commit()
    conn.close()


def get_history(session_id, limit=8):
    conn = sqlite3.connect("chatbot.db")
    rows = conn.execute(
        "SELECT role, message FROM conversations "
        "WHERE session_id=? ORDER BY id DESC LIMIT ?",
        (session_id, limit)
    ).fetchall()
    conn.close()
    return [{"role": r[0], "content": r[1]} for r in reversed(rows)]


# ─────────────────────────────────────────────
#  Sentiment analysis
# ─────────────────────────────────────────────
def analyze_sentiment_fast(text, lang="fr"):
    t = text.lower()
    pos_words = {
        "fr": ["merci","super","parfait","excellent","bravo","content","bien","ravi","fantastique","adore"],
        "en": ["thank","great","perfect","excellent","amazing","good","happy","love","wonderful","awesome"],
        "ar": ["شكر","ممتاز","رائع","جيد","سعيد","أحب","مذهل"]
    }
    neg_words = {
        "fr": ["decu","mauvais","probleme","erreur","nul","horrible","triste","fache","deteste"],
        "en": ["disappointed","bad","problem","error","terrible","horrible","sad","angry","hate","awful"],
        "ar": ["سيء","مشكلة","خطأ","رهيب","حزين","غاضب","أكره"]
    }
    p = sum(1 for w in pos_words.get(lang, pos_words["fr"]) if w in t)
    n = sum(1 for w in neg_words.get(lang, neg_words["fr"]) if w in t)
    score = max(-1.0, min(1.0, (p - n) / 4.0))
    label = "positif" if score >= 0.25 else "negatif" if score <= -0.25 else "neutre"
    return round(score, 2), label, int(abs(score) * 100)


def analyze_sentiment_llm(text, lang="fr"):
    if not os.environ.get("GROQ_API_KEY"):
        return analyze_sentiment_fast(text, lang)
    try:
        r = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": SENTIMENT_PROMPTS.get(lang, SENTIMENT_PROMPTS["fr"])},
                {"role": "user",   "content": f'Text: "{text}"'}
            ],
            max_tokens=60, temperature=0.0
        )
        raw  = r.choices[0].message.content
        data = json.loads(raw[raw.find("{"):raw.rfind("}")+1])
        score = float(data.get("score", 0))
        label = str(data.get("label", "neutre")).lower()
        pct   = int(data.get("percentage", abs(score) * 100))
        lmap  = {"positive": "positif", "neutral": "neutre", "negative": "negatif"}
        label = lmap.get(label, label)
        if label not in ("positif", "neutre", "negatif"):
            label = "positif" if score >= 0.25 else "negatif" if score <= -0.25 else "neutre"
        return round(max(-1.0, min(1.0, score)), 2), label, max(0, min(100, pct))
    except Exception:
        return analyze_sentiment_fast(text, lang)


# ─────────────────────────────────────────────
#  Local fallback replies
# ─────────────────────────────────────────────
def _local_reply(msg, lang="fr"):
    m = msg.lower()
    r = LOCAL_REPLIES.get(lang, LOCAL_REPLIES["fr"])
    greet = {"fr": ["bonjour","salut","coucou"],   "en": ["hello","hi","hey"],       "ar": ["مرحبا","أهلاً"]}
    thanks = {"fr": ["merci"],                      "en": ["thank","thanks"],         "ar": ["شكر","شكراً"]}
    hours  = {"fr": ["horaire"],                    "en": ["hour","schedule","open"], "ar": ["ساعات","مواعيد"]}
    passw  = {"fr": ["mot de passe"],               "en": ["password","forgot"],      "ar": ["كلمة المرور"]}
    if any(w in m for w in greet.get(lang, [])):  return r["hello"]
    if any(w in m for w in thanks.get(lang, [])): return r["thanks"]
    if any(w in m for w in hours.get(lang, [])):  return r["hours"]
    if any(w in m for w in passw.get(lang, [])):  return r["password"]
    return r["default"]


# ─────────────────────────────────────────────
#  Chat routes
# ─────────────────────────────────────────────
@app.route("/")
def index():
    if "session_id" not in session:
        session["session_id"] = str(uuid.uuid4())
    return render_template("index.html")


@app.route("/chat", methods=["POST"])
def chat():
    try:
        data    = request.get_json()
        user_msg = data.get("message", "").strip()
        lang    = data.get("lang", "fr")
        if lang not in ("fr", "en", "ar"):
            lang = "fr"
        if not user_msg:
            return jsonify({"error": "Empty message"}), 400

        session_id = session.get("session_id", str(uuid.uuid4()))
        score, label, pct = analyze_sentiment_llm(user_msg, lang)
        save_message(session_id, "user", user_msg, score, label, lang)

        if os.environ.get("GROQ_API_KEY"):
            history = get_history(session_id, limit=8)
            resp = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "system", "content": SYSTEM_PROMPTS.get(lang, SYSTEM_PROMPTS["fr"])},
                          *history],
                max_tokens=120, temperature=0.7
            )
            bot_reply = resp.choices[0].message.content.strip()
        else:
            bot_reply = _local_reply(user_msg, lang)

        save_message(session_id, "assistant", bot_reply, language=lang)
        return jsonify({
            "reply":     bot_reply,
            "sentiment": {"score": score, "label": label, "percentage": pct},
            "tts_lang":  TTS_LANG.get(lang, "fr-FR")
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/welcome", methods=["POST"])
def welcome():
    data = request.get_json()
    lang = data.get("lang", "fr")
    if lang not in WELCOME_MSG:
        lang = "fr"
    return jsonify({"message": WELCOME_MSG[lang], "tts_lang": TTS_LANG.get(lang, "fr-FR")})


@app.route("/transcribe", methods=["POST"])
def transcribe_audio():
    if "audio" not in request.files:
        return jsonify({"error": "No audio file"}), 400
    audio_file = request.files["audio"]
    lang = request.form.get("lang", "fr")
    if not os.environ.get("GROQ_API_KEY"):
        return jsonify({"error": "GROQ_API_KEY missing"}), 500
    try:
        audio_file.stream.seek(0)
        tr = client.audio.transcriptions.create(
            model="whisper-large-v3",
            file=(audio_file.filename, audio_file.stream, audio_file.content_type),
            language=WHISPER_LANG.get(lang, "fr")
        )
        return jsonify({"transcript": getattr(tr, "text", "") or ""})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/reset", methods=["POST"])
def reset():
    session["session_id"] = str(uuid.uuid4())
    return jsonify({"status": "ok"})


# ─────────────────────────────────────────────
#  History routes  (NEW — Jour 5)
# ─────────────────────────────────────────────
@app.route("/history")
def history_page():
    """User-facing conversation history page."""
    session_id = session.get("session_id")
    if not session_id:
        return redirect(url_for("index"))
    conn = get_db()
    rows = conn.execute(
        "SELECT role, message, sentiment_score, sentiment_label, language, created_at "
        "FROM conversations WHERE session_id=? ORDER BY id",
        (session_id,)
    ).fetchall()
    conn.close()
    messages = [dict(r) for r in rows]
    return render_template("history.html", messages=messages, session_id=session_id)


@app.route("/history/json")
def history_json():
    """Return current session history as JSON."""
    session_id = session.get("session_id")
    if not session_id:
        return jsonify([])
    conn = get_db()
    rows = conn.execute(
        "SELECT role, message, sentiment_score, sentiment_label, language, created_at "
        "FROM conversations WHERE session_id=? ORDER BY id",
        (session_id,)
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/history/export/pdf")
def export_pdf():
    """Export current session as a styled HTML → downloadable PDF via browser print."""
    session_id = session.get("session_id")
    if not session_id:
        return redirect(url_for("index"))
    conn = get_db()
    rows = conn.execute(
        "SELECT role, message, sentiment_score, sentiment_label, language, created_at "
        "FROM conversations WHERE session_id=? ORDER BY id",
        (session_id,)
    ).fetchall()
    conn.close()
    messages = [dict(r) for r in rows]
    html = render_template("export_pdf.html", messages=messages,
                           session_id=session_id,
                           exported_at=datetime.now().strftime("%d/%m/%Y %H:%M"))
    resp = make_response(html)
    resp.headers["Content-Type"] = "text/html; charset=utf-8"
    return resp


@app.route("/history/export/csv")
def export_csv():
    """Export current session as CSV download."""
    session_id = session.get("session_id")
    if not session_id:
        return redirect(url_for("index"))
    conn = get_db()
    rows = conn.execute(
        "SELECT role, message, sentiment_score, sentiment_label, language, created_at "
        "FROM conversations WHERE session_id=? ORDER BY id",
        (session_id,)
    ).fetchall()
    conn.close()
    lines = ["role,message,sentiment_label,sentiment_score,language,created_at"]
    for r in rows:
        msg = r["message"].replace('"', '""')
        lines.append(f'"{r["role"]}","{msg}","{r["sentiment_label"] or ""}","{r["sentiment_score"] or ""}","{r["language"] or "fr"}","{r["created_at"]}"')
    csv_data = "\n".join(lines)
    resp = make_response(csv_data)
    resp.headers["Content-Disposition"] = f"attachment; filename=lumia_{session_id[:8]}.csv"
    resp.headers["Content-Type"] = "text/csv; charset=utf-8"
    return resp


# ─────────────────────────────────────────────
#  Admin routes
# ─────────────────────────────────────────────
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    error = None
    if request.method == "POST":
        if (request.form.get("username") == ADMIN_USERNAME and
                request.form.get("password") == ADMIN_PASSWORD):
            session["admin"] = True
            return redirect(url_for("admin_dashboard"))
        error = "Identifiants incorrects"
    return render_template("admin_login.html", error=error)


@app.route("/admin/logout")
def admin_logout():
    session.pop("admin", None)
    return redirect(url_for("admin_login"))


@app.route("/admin")
@admin_required
def admin_dashboard():
    return render_template("admin_dashboard.html")


@app.route("/admin/stats")
@admin_required
def admin_stats():
    conn = get_db()
    total_msg  = conn.execute("SELECT COUNT(*) as c FROM conversations").fetchone()["c"]
    total_sess = conn.execute("SELECT COUNT(*) as c FROM sessions_info").fetchone()["c"]
    user_msg   = conn.execute("SELECT COUNT(*) as c FROM conversations WHERE role='user'").fetchone()["c"]
    bot_msg    = conn.execute("SELECT COUNT(*) as c FROM conversations WHERE role='assistant'").fetchone()["c"]
    avg        = round(user_msg / total_sess, 1) if total_sess else 0

    sent_rows = conn.execute("""
        SELECT sentiment_label, COUNT(*) as count FROM conversations
        WHERE role='user' AND sentiment_label IS NOT NULL GROUP BY sentiment_label
    """).fetchall()
    sentiments = {r["sentiment_label"]: r["count"] for r in sent_rows}

    lang_rows = conn.execute("""
        SELECT language, COUNT(*) as count FROM conversations
        WHERE role='user' GROUP BY language
    """).fetchall()
    languages = {(r["language"] or "fr"): r["count"] for r in lang_rows}

    daily_rows = conn.execute("""
        SELECT substr(created_at,1,10) as day, COUNT(*) as count
        FROM conversations WHERE role='user'
        GROUP BY day ORDER BY day DESC LIMIT 7
    """).fetchall()
    daily = [{"day": r["day"], "count": r["count"]} for r in reversed(daily_rows)]

    hourly_rows = conn.execute("""
        SELECT substr(created_at,12,2) as hour, AVG(sentiment_score) as avg_score
        FROM conversations
        WHERE role='user' AND sentiment_score IS NOT NULL
          AND created_at >= datetime('now','-1 day')
        GROUP BY hour ORDER BY hour
    """).fetchall()
    hourly = [{"hour": r["hour"]+"h", "score": round(r["avg_score"], 2)} for r in hourly_rows]

    recent_rows = conn.execute("""
        SELECT message, sentiment_label, sentiment_score, language, created_at
        FROM conversations WHERE role='user' AND sentiment_label IS NOT NULL
        ORDER BY id DESC LIMIT 20
    """).fetchall()
    recent = [{
        "text":  r["message"][:100],
        "label": r["sentiment_label"],
        "score": round(r["sentiment_score"], 2) if r["sentiment_score"] else 0,
        "lang":  r["language"] or "fr",
        "time":  r["created_at"][:16].replace("T", " ")
    } for r in recent_rows]

    pos = sentiments.get("positif", 0)
    neu = sentiments.get("neutre", 0)
    neg = sentiments.get("negatif", 0)
    satisfaction = round(pos / (pos + neu + neg or 1) * 100)
    conn.close()

    return jsonify({
        "totals":    {"sessions": total_sess, "messages": total_msg,
                      "userMessages": user_msg, "botMessages": bot_msg,
                      "avgPerSession": avg, "satisfaction": satisfaction},
        "sentiments": {"positif": pos, "neutre": neu, "negatif": neg},
        "languages":  languages,
        "daily":      daily,
        "hourly":     hourly,
        "recent":     recent
    })


@app.route("/admin/sessions")
@admin_required
def admin_sessions():
    """Paginated session list for admin."""
    page = int(request.args.get("page", 1))
    per_page = 20
    offset = (page - 1) * per_page
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) as c FROM sessions_info").fetchone()["c"]
    rows = conn.execute("""
        SELECT s.session_id, s.first_seen, s.last_seen, s.message_count, s.language,
               (SELECT message FROM conversations
                WHERE session_id=s.session_id AND role='user' ORDER BY id LIMIT 1) as first_msg
        FROM sessions_info s ORDER BY s.last_seen DESC LIMIT ? OFFSET ?
    """, (per_page, offset)).fetchall()
    conn.close()
    return jsonify({
        "sessions": [dict(r) for r in rows],
        "total": total, "page": page, "per_page": per_page
    })


@app.route("/admin/conversation/<session_id>")
@admin_required
def admin_conversation(session_id):
    conn = get_db()
    messages = conn.execute(
        "SELECT role, message, sentiment_score, sentiment_label, created_at "
        "FROM conversations WHERE session_id=? ORDER BY id",
        (session_id,)
    ).fetchall()
    conn.close()
    return render_template("admin_conversation.html", messages=messages, session_id=session_id)


@app.route("/admin/export/pdf/<session_id>")
@admin_required
def admin_export_pdf(session_id):
    """Admin export any session as PDF-ready HTML."""
    conn = get_db()
    rows = conn.execute(
        "SELECT role, message, sentiment_score, sentiment_label, language, created_at "
        "FROM conversations WHERE session_id=? ORDER BY id",
        (session_id,)
    ).fetchall()
    conn.close()
    messages = [dict(r) for r in rows]
    html = render_template("export_pdf.html", messages=messages,
                           session_id=session_id,
                           exported_at=datetime.now().strftime("%d/%m/%Y %H:%M"))
    resp = make_response(html)
    resp.headers["Content-Type"] = "text/html; charset=utf-8"
    return resp


@app.route("/admin/export/csv/<session_id>")
@admin_required
def admin_export_csv(session_id):
    """Admin export any session as CSV."""
    conn = get_db()
    rows = conn.execute(
        "SELECT role, message, sentiment_score, sentiment_label, language, created_at "
        "FROM conversations WHERE session_id=? ORDER BY id",
        (session_id,)
    ).fetchall()
    conn.close()
    lines = ["role,message,sentiment_label,sentiment_score,language,created_at"]
    for r in rows:
        msg = r["message"].replace('"', '""')
        lines.append(f'"{r["role"]}","{msg}","{r["sentiment_label"] or ""}","{r["sentiment_score"] or ""}","{r["language"] or "fr"}","{r["created_at"]}"')
    resp = make_response("\n".join(lines))
    resp.headers["Content-Disposition"] = f"attachment; filename=session_{session_id[:8]}.csv"
    resp.headers["Content-Type"] = "text/csv; charset=utf-8"
    return resp


if __name__ == "__main__":
    init_db()
    print("🚀 http://localhost:5000")
    print("📋 Historique : http://localhost:5000/history")
    print("📊 Admin      : http://localhost:5000/admin  (admin/admin123)")
    app.run(debug=True, host="127.0.0.1", port=5000)
