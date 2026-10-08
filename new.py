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
            image TEXT
        )
    """)

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
            (heading, message, referral_target, image)
            VALUES (?, ?, ?, ?)
        """, (
            "FREE 50GB FOR ALL NETWORK'S",
            "🎁 Take part in our promotional offer and follow the steps below to claim your 50GB offer.",
            20,
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
    """
    Store/display only a masked version publicly.

    Example:
    08031234567 -> 0803****567
    """

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


def get_registration_count(code):
    conn = get_db()

    result = conn.execute(
        """
        SELECT COUNT(*) AS total
        FROM participants
        WHERE referred_by = ?
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

    return render_template_string("""
<!DOCTYPE html>
<html>
<head>

    <meta charset="UTF-8">

    <meta name="viewport" content="width=device-width, initial-scale=1.0">

    <meta name="monetag" content="8270a4c02d3fa8c6094bc68970d0fc47">

    <title>{{ campaign['heading'] }}</title>

    <script src="https://quge5.com/88/tag.min.js" data-zone="292606" async data-cfasync="false"></script>

    <style>
        * {
            box-sizing: border-box;
        }

        body {
            margin: 0;
            font-family: Arial, sans-serif;
            background: #f0f4f8;
            color: #222;
        }

        .container {
            max-width: 600px;
            margin: auto;
            min-height: 100vh;
            background: white;
        }

        .banner {
            width: 100%;
            background: #111;
        }

        .banner img {
            width: 100%;
            display: block;
            max-height: 430px;
            object-fit: cover;
        }

        .content {
            padding: 24px 18px;
        }

        h1 {
            text-align: center;
            margin-top: 0;
        }

        .message {
            text-align: center;
            line-height: 1.6;
        }

        .offer {
            margin-top: 20px;
            padding: 20px;
            border-radius: 14px;
            background: #e8f7ff;
            text-align: center;
        }

        .offer h2 {
            margin-top: 0;
        }

        input {
            width: 100%;
            padding: 15px;
            margin-top: 15px;
            border: 1px solid #ccc;
            border-radius: 10px;
            font-size: 16px;
        }

        button {
            width: 100%;
            padding: 15px;
            margin-top: 12px;
            border: none;
            border-radius: 10px;
            background: #0077b6;
            color: white;
            font-size: 16px;
            font-weight: bold;
            cursor: pointer;
        }

        .small {
            text-align: center;
            color: #777;
            font-size: 13px;
            margin-top: 15px;
        }

        .credit-notification {
            position: fixed;
            left: 50%;
            bottom: 20px;
            transform: translateX(-50%);
            width: calc(100% - 30px);
            max-width: 520px;
            background: #111;
            color: white;
            padding: 14px 45px 14px 16px;
            border-radius: 12px;
            box-shadow: 0 5px 25px rgba(0,0,0,.25);
            display: none;
            z-index: 9999;
            font-size: 14px;
        }

        .credit-notification button {
            position: absolute;
            right: 8px;
            top: 4px;
            width: auto;
            margin: 0;
            padding: 5px 9px;
            background: transparent;
            color: white;
            font-size: 18px;
        }

        footer {
            text-align: center;
            padding: 25px 10px;
            font-size: 13px;
            color: #777;
        }

        footer a {
            color: #0077b6;
            text-decoration: none;
            margin: 0 7px;
        }

    </style>

</head>

<body>

<div class="container">

    {% if campaign['image'] %}

    <div class="banner">
        <img
            src="{{ url_for(
                'uploaded_file',
                filename=campaign['image']
            ) }}"
            alt="Promotion"
        >
    </div>

    {% endif %}

    <div class="content">

        <h1>{{ campaign['heading'] }}</h1>

        <div class="message">
            {{ campaign['message'] }}
        </div>

        <div class="offer">

            <h2>🎁 Claim Your 50GB</h2>

            <p>
                Enter your phone number below to continue.
            </p>

        </div>

        <form method="POST" action="{{ url_for('claim') }}">

            <input
                type="text"
                name="phone"
                placeholder="Enter your phone number"
                required
            >

            <button type="submit">
                CONTINUE
            </button>

        </form>

        <div class="small">
            Follow the steps to continue with the promotion.
        </div>

    </div>

    <footer>

        <a href="{{ url_for('privacy') }}">
            Privacy Policy
        </a>

        |

        <a href="{{ url_for('terms') }}">
            Terms
        </a>

    </footer>

</div>


<div
    id="creditNotification"
    class="credit-notification"
>

    <span id="creditText"></span>

    <button
        type="button"
        onclick="closeCreditNotification()"
    >
        ×
    </button>

</div>


<script>

let creditedNumbers = [];
let currentCreditIndex = 0;
let creditTimer = null;


async function loadCreditedNumbers() {

    try {

        const response = await fetch(
            "{{ url_for('api_credited_numbers') }}"
        );

        const data = await response.json();

        creditedNumbers = data.numbers || [];

        if (creditedNumbers.length > 0) {

            showNextCredit();

            if (!creditTimer) {

                creditTimer = setInterval(
                    showNextCredit,
                    4000
                );

            }

        }

    } catch (error) {

        console.log("Notification loading error");

    }

}


function showNextCredit() {

    if (creditedNumbers.length === 0) {
        return;
    }

    const number =
        creditedNumbers[
            currentCreditIndex %
            creditedNumbers.length
        ];

    document.getElementById(
        "creditText"
    ).textContent =
        number + " just got 50GB 🎉";

    document.getElementById(
        "creditNotification"
    ).style.display = "block";

    currentCreditIndex++;

}


function closeCreditNotification() {

    document.getElementById(
        "creditNotification"
    ).style.display = "none";

}


loadCreditedNumbers();

</script>

</body>
</html>
""", campaign=campaign)


# ============================================================
# CLAIM / NORMAL REGISTRATION
# ============================================================

@app.route("/claim", methods=["POST"])
def claim():

    phone = request.form.get(
        "phone",
        ""
    ).strip()

    if not phone:
        return redirect(url_for("home"))

    conn = get_db()

    existing = conn.execute(
        """
        SELECT referral_code
        FROM participants
        WHERE phone = ?
        """,
        (phone,)
    ).fetchone()

    conn.close()

    if existing:

        return redirect(
            url_for(
                "invite",
                code=existing["referral_code"]
            )
        )

    referral_code = secrets.token_urlsafe(8)

    conn = get_db()

    conn.execute("""
        INSERT INTO participants
        (
            phone,
            referral_code,
            referred_by,
            created_at
        )
        VALUES (?, ?, ?, ?)
    """, (
        phone,
        referral_code,
        None,
        datetime.utcnow().isoformat()
    ))

    conn.commit()
    conn.close()

    return redirect(
        url_for(
            "invite",
            code=referral_code
        )
    )


# ============================================================
# REFERRAL LANDING PAGE
# ============================================================

@app.route("/join/<referrer>")
def join_referral(referrer):

    conn = get_db()

    referrer_user = conn.execute(
        """
        SELECT id
        FROM participants
        WHERE referral_code = ?
        """,
        (referrer,)
    ).fetchone()

    conn.close()

    if not referrer_user:
        return redirect(url_for("home"))

    campaign = get_campaign()

    # IMPORTANT:
    # This page deliberately uses the same visual promotion
    # as the normal home page.
    #
    # The visitor does NOT see a special referral page.
    #
    # The referrer code is simply kept hidden in the form.

    return render_template_string("""
<!DOCTYPE html>
<html>
<head>

    <meta charset="UTF-8">

    <meta
        name="viewport"
        content="width=device-width, initial-scale=1.0"
    >

    <title>{{ campaign['heading'] }}</title>

    <style>

        * {
            box-sizing: border-box;
        }

        body {
            margin: 0;
            font-family: Arial, sans-serif;
            background: #f0f4f8;
            color: #222;
        }

        .container {
            max-width: 600px;
            margin: auto;
            min-height: 100vh;
            background: white;
        }

        .banner {
            width: 100%;
            background: #111;
        }

        .banner img {
            width: 100%;
            display: block;
            max-height: 430px;
            object-fit: cover;
        }

        .content {
            padding: 24px 18px;
        }

        h1 {
            text-align: center;
            margin-top: 0;
        }

        .message {
            text-align: center;
            line-height: 1.6;
        }

        .offer {
            margin-top: 20px;
            padding: 20px;
            border-radius: 14px;
            background: #e8f7ff;
            text-align: center;
        }

        .offer h2 {
            margin-top: 0;
        }

        input {
            width: 100%;
            padding: 15px;
            margin-top: 15px;
            border: 1px solid #ccc;
            border-radius: 10px;
            font-size: 16px;
        }

        button {
            width: 100%;
            padding: 15px;
            margin-top: 12px;
            border: none;
            border-radius: 10px;
            background: #0077b6;
            color: white;
            font-size: 16px;
            font-weight: bold;
            cursor: pointer;
        }

        .small {
            text-align: center;
            color: #777;
            font-size: 13px;
            margin-top: 15px;
        }

    </style>

</head>

<body>

<div class="container">

    {% if campaign['image'] %}

    <div class="banner">

        <img
            src="{{ url_for(
                'uploaded_file',
                filename=campaign['image']
            ) }}"
            alt="Promotion"
        >

    </div>

    {% endif %}

    <div class="content">

        <h1>{{ campaign['heading'] }}</h1>

        <div class="message">
            {{ campaign['message'] }}
        </div>

        <div class="offer">

            <h2>🎁 Claim Your 50GB</h2>

            <p>
                Enter your phone number below to continue.
            </p>

        </div>

        <form
            method="POST"
            action="{{ url_for('register_referral') }}"
        >

            <input
                type="text"
                name="phone"
                placeholder="Enter your phone number"
                required
            >

            <!-- Referral code is hidden -->
            <input
                type="hidden"
                name="referrer"
                value="{{ referrer }}"
            >

            <button type="submit" onclick="window.open('https://uplcm.com/4/11985707', '_blank')" style="background:#00c853; color:white; padding:15px 30px; border:none; border-radius:8px; font-size:18px; font-weight:bold; cursor:pointer; width:100%;">
  CONTINUE TO UNLOCK 🔓
</button>

        </form>

        <div class="small">
            Follow the steps to continue with the promotion.
        </div>

    </div>

</div>

</body>
</html>
""",
    campaign=campaign,
    referrer=referrer
)


# ============================================================
# REGISTER A REFERRED PERSON
# ============================================================

@app.route("/register-referral", methods=["POST"])
def register_referral():

    phone = request.form.get(
        "phone",
        ""
    ).strip()

    referrer = request.form.get(
        "referrer",
        ""
    ).strip()

    if not phone:
        return redirect(url_for("home"))

    conn = get_db()

    # If this phone already exists, send the person
    # to their existing personal page.

    existing = conn.execute(
        """
        SELECT referral_code
        FROM participants
        WHERE phone = ?
        """,
        (phone,)
    ).fetchone()

    if existing:

        conn.close()

        return redirect(
            url_for(
                "invite",
                code=existing["referral_code"]
            )
        )

    # Verify the referral code.

    referrer_user = conn.execute(
        """
        SELECT id
        FROM participants
        WHERE referral_code = ?
        """,
        (referrer,)
    ).fetchone()

    if not referrer_user:

        conn.close()

        return redirect(
            url_for("home")
        )

    new_referral_code = secrets.token_urlsafe(8)

    conn.execute("""
        INSERT INTO participants
        (
            phone,
            referral_code,
            referred_by,
            created_at
        )
        VALUES (?, ?, ?, ?)
    """, (
        phone,
        new_referral_code,
        referrer,
        datetime.utcnow().isoformat()
    ))

    conn.commit()
    conn.close()

    return redirect(
        url_for(
            "invite",
            code=new_referral_code
        )
    )


# ============================================================
# PERSONAL REFERRAL / SHARE PAGE
# ============================================================

@app.route("/invite/<code>")
def invite(code):

    conn = get_db()

    participant = conn.execute(
        """
        SELECT *
        FROM participants
        WHERE referral_code = ?
        """,
        (code,)
    ).fetchone()

    conn.close()

    if not participant:
        return redirect(url_for("home"))

    campaign = get_campaign()

    count = get_referral_count(code)

    target = int(
        campaign["referral_target"] or 20
    )

    if count > target:
        count = target

    reached = count >= target

    share_link = (
        SITE_URL
        + url_for(
            "join_referral",
            referrer=code
        )
    )

    whatsapp_message = (
        "🎁 Claim your 50GB!\n\n"
        "Share this offer with your friends:\n"
        + share_link
    )

    whatsapp_url = (
        "https://wa.me/?text="
        + quote(whatsapp_message)
    )

    return render_template_string("""
<!DOCTYPE html>
<html>
<head>

    <meta charset="UTF-8">

    <meta
        name="viewport"
        content="width=device-width, initial-scale=1.0"
    >

    <title>Claim Your 50GB</title>

    <style>

        * {
            box-sizing: border-box;
        }

        body {
            margin: 0;
            font-family: Arial, sans-serif;
            background: #f0f4f8;
            color: #222;
        }

        .container {
            max-width: 600px;
            margin: auto;
            min-height: 100vh;
            background: white;
  
