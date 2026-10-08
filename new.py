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
    flash
)
from werkzeug.utils import secure_filename


# ============================================================
# APP SETTINGS
# ============================================================

app = Flask(__name__)

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "2009/30"
)

ADMIN_USERNAME = os.environ.get(
    "ADMIN_USERNAME",
    "admin"
)

ADMIN_PASSWORD = os.environ.get(
    "ADMIN_PASSWORD",
    "JEPHTHAH"
)

DATABASE = "promotion.db"
UPLOAD_FOLDER = "uploads"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024

ALLOWED_EXTENSIONS = {
    "jpg",
    "jpeg",
    "png",
    "webp"
}


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
            id INTEGER PRIMARY KEY,
            heading TEXT NOT NULL,
            message TEXT NOT NULL,
            referral_target INTEGER NOT NULL DEFAULT 20,
            image TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS participants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone TEXT UNIQUE NOT NULL,
            referral_code TEXT UNIQUE NOT NULL,
            referred_by TEXT,
            created_at TEXT NOT NULL
        )
    """)

    campaign = conn.execute(
        "SELECT id FROM campaign WHERE id = 1"
    ).fetchone()

    if not campaign:

        conn.execute("""
            INSERT INTO campaign
            (
                id,
                heading,
                message,
                referral_target,
                image
            )
            VALUES (?, ?, ?, ?, ?)
        """, (
            1,
            "",
            "",
            20,
            None
        ))

    conn.commit()
    conn.close()


setup_database()


# ============================================================
# HELPERS
# ============================================================

def get_campaign():

    conn = get_db()

    campaign = conn.execute(
        "SELECT * FROM campaign WHERE id = 1"
    ).fetchone()

    conn.close()

    return campaign


def allowed_file(filename):

    return (
        "." in filename
        and filename.rsplit(
            ".",
            1
        )[1].lower() in ALLOWED_EXTENSIONS
    )


def admin_required(function):

    @wraps(function)
    def wrapper(*args, **kwargs):

        if not session.get("admin_logged_in"):
            return redirect(
                url_for("admin_login")
            )

        return function(*args, **kwargs)

    return wrapper


def get_referral_count(code):

    conn = get_db()

    result = conn.execute(
        """
        SELECT COUNT(*)
        FROM participants
        WHERE referred_by = ?
        """,
        (code,)
    ).fetchone()

    conn.close()

    return result[0]


# ============================================================
# PUBLIC HOME PAGE
# ============================================================

HOME_PAGE = """
<!DOCTYPE html>

<html>

<head>

<meta name="viewport"
      content="width=device-width, initial-scale=1">

<title>{{ campaign['heading'] or 'Promotional Offer' }}</title>

<style>

* {
    box-sizing: border-box;
}

body {

    margin: 0;

    padding: 0;

    font-family: Arial, sans-serif;

    color: #172033;

    background:
        linear-gradient(
            135deg,
            #dff7ff,
            #f8fcff,
            #fff8d6
        );
}


/* =========================================
   MAIN CONTAINER
   ========================================= */

.container {

    width: 94%;

    max-width: 600px;

    margin: 20px auto 45px;

}


/* =========================================
   ADMIN IMAGE + ADMIN TEXT
   ========================================= */

.hero {

    background: white;

    border-radius: 22px;

    overflow: hidden;

    margin-bottom: 20px;

    box-shadow:
        0 12px 35px
        rgba(0, 150, 255, 0.18);

    animation:
        floating 4s ease-in-out infinite;

}


/* =========================================
   IMAGE
   ========================================= */

.hero-image {

    width: 100%;

    display: block;

    max-height: 430px;

    object-fit: cover;

}


/* =========================================
   ADMIN TEXT
   ========================================= */

.hero-content {

    padding: 25px 22px 30px;

    text-align: center;

    background:
        linear-gradient(
            180deg,
            #ffffff,
            #effbff
        );

}


.hero-content h1 {

    margin: 0 0 14px;

    font-size: 30px;

    line-height: 1.2;

    font-weight: 900;

    color: #008bd2;

    text-shadow:
        0 3px 10px
        rgba(0, 139, 210, 0.18);

}


.hero-content p {

    margin: 0;

    font-size: 18px;

    line-height: 1.6;

    font-weight: 700;

    color: #172033;

    white-space: pre-line;

}


/* =========================================
   FLOATING ANIMATION
   ========================================= */

@keyframes floating {

    0% {
        transform: translateY(0);
    }

    50% {
        transform: translateY(-7px);
    }

    100% {
        transform: translateY(0);
    }

}


/* =========================================
   OFFER CARD
   ========================================= */

.offer {

    position: relative;

    overflow: hidden;

    background: white;

    border-radius: 22px;

    padding: 28px 22px;

    text-align: center;

    box-shadow:
        0 12px 35px
        rgba(0, 150, 255, 0.16);

    animation:
        floating 4.5s ease-in-out infinite;

}


/* =========================================
   DECORATIVE WATER EFFECT
   ========================================= */

.offer::before {

    content: "";

    position: absolute;

    width: 190px;

    height: 190px;

    border-radius: 50%;

    background:
        rgba(0, 174, 255, 0.12);

    top: -90px;

    left: -70px;

    animation:
        waterMove 5s ease-in-out infinite;

}


.offer::after {

    content: "";

    position: absolute;

    width: 170px;

    height: 170px;

    border-radius: 50%;

    background:
        rgba(255, 210, 0, 0.14);

    right: -70px;

    bottom: -90px;

    animation:
        waterMove 6s ease-in-out infinite reverse;

}


@keyframes waterMove {

    0% {
        transform: translate(0, 0);
    }

    50% {
        transform: translate(20px, -12px);
    }

    100% {
        transform: translate(0, 0);
    }

}


.offer > * {

    position: relative;

    z-index: 2;

}


/* =========================================
   OFFER HEADING
   ========================================= */

.offer h2 {

    margin-top: 0;

    color: #008bd2;

    font-size: 22px;

    font-weight: 900;

}


/* =========================================
   50GB
   ========================================= */

.gb {

    font-size: 58px;

    font-weight: 900;

    color: #f4b400;

    margin: 8px 0;

    text-shadow:
        0 3px 10px
        rgba(244, 180, 0, 0.25);

    animation:
        gbFloat 3s ease-in-out infinite;

}


@keyframes gbFloat {

    0% {
        transform: translateY(0);
    }

    50% {
        transform: translateY(-6px);
    }

    100% {
        transform: translateY(0);
    }

}


.subtitle {

    color: #596579;

    margin-bottom: 24px;

    font-weight: 600;

}


/* =========================================
   PHONE INPUT
   ========================================= */

input {

    width: 100%;

    padding: 16px;

    border:
        2px solid #d7eefa;

    border-radius: 13px;

    font-size: 16px;

    margin-bottom: 13px;

    outline: none;

}


input:focus {

    border-color: #00a8ff;

    box-shadow:
        0 0 0 4px
        rgba(0, 168, 255, 0.12);

}


/* =========================================
   CLAIM BUTTON
   ========================================= */

button {

    width: 100%;

    padding: 16px;

    border: none;

    border-radius: 13px;

    font-size: 17px;

    font-weight: 900;

    cursor: pointer;

}


.claim {

    color: white;

    background:
        linear-gradient(
            135deg,
            #009fe3,
            #0077ff
        );

    box-shadow:
        0 8px 20px
        rgba(0, 126, 255, 0.25);

    animation:
        buttonFloat 3s ease-in-out infinite;

}


@keyframes buttonFloat {

    0% {
        transform: translateY(0);
    }

    50% {
        transform: translateY(-4px);
    }

    100% {
        transform: translateY(0);
    }

}


.claim:active {

    transform: scale(0.97);

}


/* =========================================
   INFO
   ========================================= */

.info {

    margin-top: 18px;

    color: #687386;

    font-size: 14px;

    line-height: 1.5;

}


/* =========================================
   MOBILE
   ========================================= */

@media (max-width: 480px) {

    .container {
        width: 94%;
    }

    .hero-content h1 {
        font-size: 26px;
    }

    .hero-content p {
        font-size: 16px;
    }

    .gb {
        font-size: 50px;
    }

}

</style>

</head>


<body>

<div class="container">


    <!-- ======================================
         ADMIN IMAGE + HEADING + TEXT
         ====================================== -->

    {% if campaign['image']
       or campaign['heading']
       or campaign['message'] %}

    <div class="hero">


        {% if campaign['image'] %}

        <img
            class="hero-image"
            src="{{ url_for(
                'uploaded_file',
                filename=campaign['image']
            ) }}"
            alt="Campaign image"
        >

        {% endif %}


        {% if campaign['heading']
           or campaign['message'] %}

        <div class="hero-content">


            {% if campaign['heading'] %}

            <h1>
                {{ campaign['heading'] }}
            </h1>

            {% endif %}


            {% if campaign['message'] %}

            <p>
                {{ campaign['message'] }}
            </p>

            {% endif %}


        </div>

        {% endif %}


    </div>

    {% endif %}


    <!-- ======================================
         50GB SECTION
         ====================================== -->

    <div class="offer">

        <h2>
            Available Data Offer
        </h2>


        <div class="gb">
            50GB
        </div>


        <div class="subtitle">
            Enter your phone number to continue.
        </div>


        <form
            action="{{ url_for('claim') }}"
            method="POST"
        >

            <input
                type="tel"
                name="phone"
                placeholder="Enter your phone number"
                required
            >


            <button
                class="claim"
                type="submit"
            >
                CLAIM NOW
            </button>

        </form>


        <div class="info">

            After registering, you will receive
            your personal referral link.

        </div>

    </div>


</div>

</body>

</html>
"""


# ============================================================
# HOME ROUTE
# ============================================================

@app.route("/")
def home():

    campaign = get_campaign()

    return render_template_string(
        HOME_PAGE,
        campaign=campaign
    )


# ============================================================
# CLAIM
# ============================================================

@app.route("/claim", methods=["POST"])
def claim():

    phone = request.form.get(
        "phone",
        ""
    ).strip()

    if not phone:
        return redirect(
            url_for("home")
        )

    conn = get_db()

    existing = conn.execute(
        """
        SELECT *
        FROM participants
        WHERE phone = ?
        """,
        (phone,)
    ).fetchone()

    if existing:

        referral_code = existing["referral_code"]

        conn.close()

        return redirect(
            url_for(
                "invite",
                code=referral_code
            )
        )


    referral_code = secrets.token_urlsafe(8)


    try:

        conn.execute(
            """
            INSERT INTO participants
            (
                phone,
                referral_code,
                referred_by,
                created_at
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                phone,
                referral_code,
                None,
                datetime.utcnow().isoformat()
            )
        )

        conn.commit()

    except sqlite3.IntegrityError:

        conn.close()

        return redirect(
            url_for("home")
        )


    conn.close()


    return redirect(
        url_for(
            "invite",
            code=referral_code
        )
    )


# ============================================================
# REFERRAL PAGE
# ============================================================

@app.route("/invite/<code>")
def invite(code):

    campaign = get_campaign()

    count = get_referral_count(code)

    target = campaign["referral_target"]


    share_link = (
        request.host_url.rstrip("/")
        + url_for(
            "join_referral",
            referrer=code
        )
    )


    whatsapp_message = (
        "🎁 Check out this 50GB data promotion.\n\n"
    "You can check your eligibility here:\n"
        + share_link
    )


    whatsapp_url = (
        "https://wa.me/?text="
        + quote(whatsapp_message)
    )


    page = """

<!DOCTYPE html>

<html>

<head>

<meta name="viewport"
      content="width=device-width, initial-scale=1">

<title>Referral</title>

<style>

body {

    margin: 0;

    padding: 25px;

    font-family: Arial;

    background:
        linear-gradient(
            135deg,
            #e0f7ff,
            #fff8d6
        );

}

.box {

    max-width: 500px;

    margin: 30px auto;

    background: white;

    padding: 28px;

    border-radius: 22px;

    text-align: center;

    box-shadow:
        0 12px 35px
        rgba(0, 150, 255, 0.18);

}

.count {

    font-size: 48px;

    font-weight: 900;

    color: #008bd2;

    margin: 20px;

}

a {

    display: block;

    text-decoration: none;

    padding: 16px;

    margin-top: 15px;

    border-radius: 12px;

    font-weight: 900;

}

.share {

    background: #25D366;

    color: white;

}

.home {

    background: #008bd2;

    color: white;

}

</style>

</head>


<body>

<div class="box">

<h2>
    Invite People
</h2>

<p>
    Your referral progress
</p>

<div class="count">

    {{ count }} / {{ target }}

</div>


{% if count >= target %}

<h3>
    Referral target reached!
</h3>

{% else %}

<p>
    Invite {{ target - count }}
    more people.
</p>

{% endif %}


<a
    class="share"
    href="{{ whatsapp_url }}"
    target="_blank"
>
    SHARE ON WHATSAPP
</a>


<a
    class="home"
    href="{{ url_for('home') }}"
>
    BACK TO OFFER
</a>


</div>

</body>

</html>

"""


    return render_template_string(
        page,
        count=count,
        target=target,
        whatsapp_url=whatsapp_url
    )


# ============================================================
# JOIN THROUGH REFERRAL
# ============================================================

@app.route("/join/<referrer>")
def join_referral(referrer):

    page = """

<!DOCTYPE html>

<html>

<head>

<meta name="viewport"
      content="width=device-width, initial-scale=1">

<title>Join Promotion</title>

<style>

body {

    font-family: Arial;

    background:
        linear-gradient(
            135deg,
            #e0f7ff,
            #fff8d6
        );

    padding: 25px;

}

.box {

    max-width: 500px;

    margin: 40px auto;

    background: white;

    padding: 28px;

    border-radius: 22px;

    text-align: center;

    box-shadow:
        0 12px 35px
        rgba(0, 150, 255, 0.18);

}

input {

    width: 100%;

    box-sizing: border-box;

    padding: 16px;

    margin: 15px 0;

    border-radius: 12px;

    border:
        2px solid #d7eefa;

    font-size: 16px;

}

button {

    width: 100%;

    padding: 16px;

    border: 0;

    border-radius: 12px;

    background:
        linear-gradient(
            135deg,
            #009fe3,
            #0077ff
        );

    color: white;

    font-size: 16px;

    font-weight: 900;

}

</style>

</head>


<body>

<div class="box">

<h2>
    Join the Promotion
</h2>

<p>
    Enter your phone number to continue.
</p>


<form
    action="{{ url_for('register_referral') }}"
    method="POST"
>

<input
    type="tel"
    name="phone"
    placeholder="Phone number"
    required
>


<input
    type="hidden"
    name="referrer"
    value="{{ referrer }}"
>


<button type="submit">
    CONTINUE
</button>

</form>

</div>

</body>

</html>

"""

    return render_template_string(
        page,
        referrer=referrer
    )


# ============================================================
# REGISTER REFERRAL
# ============================================================

@app.route(
    "/register-referral",
    methods=["POST"]
)
def register_referral():

    phone = request.form.get(
        "phone",
        ""
    ).strip()

    referrer = request.form.get(
        "referrer",
        ""
    ).strip()


    if not phone or not referrer:

        return redirect(
            url_for("home")
        )


    conn = get_db()


    existing = conn.execute(
        """
        SELECT *
        FROM participants
        WHERE phone = ?
        """,
        (phone,)
    ).fetchone()


    if existing:

        referral_code = existing["referral_code"]

        conn.close()

        return redirect(
            url_for(
                "invite",
                code=referral_code
            )
        )


    owner = conn.execute(
        """
        SELECT id
        FROM participants
        WHERE referral_code = ?
        """,
        (referrer,)
    ).fetchone()


    if not owner:

        conn.close()

        return redirect(
            url_for("home")
        )


    referral_code = secrets.token_urlsafe(8)


    conn.execute(
        """
        INSERT INTO participants
        (
            phone,
            referral_code,
            referred_by,
            created_at
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            phone,
            referral_code,
            referrer,
            datetime.utcnow().isoformat()
        )
    )


    conn.commit()

    conn.close()


    return redirect(
        url_for(
            "invite",
            code=referral_code
        )
    )


# ============================================================
# SERVE UPLOADED IMAGE
# ============================================================

@app.route("/uploads/<filename>")
def uploaded_file(filename):

    return send_from_directory(
        app.config["UPLOAD_FOLDER"],
        filename
    )


# ============================================================
# ADMIN LOGIN
# ============================================================

ADMIN_LOGIN = """

<!DOCTYPE html>

<html>

<head>

<meta name="viewport"
      content="width=device-width, initial-scale=1">

<title>Admin Login</title>

<style>

body {

    font-family: Arial;

    background: #111;

    padding: 30px;

}

.box {

    max-width: 400px;

    margin: 60px auto;

    background: white;

    padding: 28px;

    border-radius: 18px;

}

input {

    width: 100%;

    box-sizing: border-box;

    padding: 15px;

    margin: 8px 0;

    border:
        1px solid #ddd;

    border-radius: 10px;

}

button {

    width: 100%;

    padding: 15px;

    background: #008bd2;

    color: white;

    border: 0;

    border-radius: 10px;

    margin-top: 10px;

    font-weight: bold;

}

.error {

    color: red;

}

</style>

</head>


<body>

<div class="box">

<h2>
    Admin Login
</h2>


{% with messages = get_flashed_messages() %}

{% for message in messages %}

<p class="error">
    {{ message }}
</p>

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

"""


@app.route(
    "/secret-admin",
    methods=["GET", "POST"]
)
def admin_login():

    if request.method == "POST":

        username = request.form.get(
            "username",
            ""
        )

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
                url_for(
                    "admin_dashboard"
                )
            )


        flash(
            "Invalid username or password."
        )


    return render_template_string(
        ADMIN_LOGIN
    )


# ============================================================
# ADMIN DASHBOARD
# ============================================================

ADMIN_DASHBOARD = """

<!DOCTYPE html>

<html>

<head>

<meta name="viewport"
      content="width=device-width, initial-scale=1">

<title>Admin Dashboard</title>

<style>

body {

    font-family: Arial;

    background: #f2f7fa;

    margin: 0;

    padding: 20px;

}

.container {

    max-width: 800px;

    margin: auto;

}

.card {

    background: white;

    padding: 22px;

    margin-bottom: 18px;

    border-radius: 18px;

    box-shadow:
        0 8px 25px
        rgba(0, 100, 150, 0.08);

}

.stat {

    font-size: 38px;

    font-weight: 900;

    color: #008bd2;

}

a {

    display: inline-block;

    padding: 13px 18px;

    border-radius: 10px;

    text-decoration: none;

    background: #008bd2;

    color: white;

    font-weight: bold;

    margin-top: 8px;

}

img {

    width: 100%;

    max-height: 350px;

    object-fit: cover;

    border-radius: 13px;

}

table {

    width: 100%;

    border-collapse: collapse;

}

td,
th {

    padding: 10px;

    border-bottom:
        1px solid #ddd;

    text-align: left;

}

</style>

</head>


<body>

<div class="container">

<h1>
    Admin Dashboard
</h1>


<div class="card">

<h3>
    Total Participants
</h3>

<div class="stat">
    {{ total }}
</div>

</div>


<div class="card">

<h2>
    Current Campaign
</h2>


{% if campaign['image'] %}

<img
    src="{{ url_for(
        'uploaded_file',
        filename=campaign['image']
    ) }}"
>

{% endif %}


{% if campaign['heading'] %}

<h2>
    {{ campaign['heading'] }}
</h2>

{% endif %}


{% if campaign['message'] %}

<p>
    {{ campaign['message'] }}
</p>

{% endif %}


<p>

Referral target:

<strong>
    {{ campaign['referral_target'] }}
</strong>

</p>


<a href="{{ url_for('edit_campaign') }}">
    EDIT / POST CAMPAIGN
</a>

</div>


<div class="card">

<h2>
    Recent Participants
</h2>


<table>

<tr>

<th>
    Phone
</th>

<th>
    Date
</th>

</tr>


{% for user in participants %}

<tr>

<td>
    {{ user['phone'] }}
</td>

<td>
    {{ user['created_at'][:19] }}
</td>

</tr>

{% endfor %}

</table>

</div>


<a href="{{ url_for('admin_logout') }}">
    LOGOUT
</a>


</div>

</body>

</html>

"""


@app.route(
    "/secret-admin/dashboard"
)
@admin_required
def admin_dashboard():

    conn = get_db()


    total = conn.execute(
        "SELECT COUNT(*) FROM participants"
    ).fetchone()[0]


    participants = conn.execute(
        """
        SELECT phone, created_at
        FROM participants
        ORDER BY id DESC
        LIMIT 50
        """
    ).fetchall()


    conn.close()


    campaign = get_campaign()


    return render_template_string(
        ADMIN_DASHBOARD,
        total=total,
        participants=participants,
        campaign=campaign
    )


# ============================================================
# ADMIN CAMPAIGN EDITOR
# ============================================================

EDIT_CAMPAIGN = """

<!DOCTYPE html>

<html>

<head>

<meta name="viewport"
      content="width=device-width, initial-scale=1">

<title>Post Campaign</title>

<style>

body {

    font-family: Arial;

    background: #f2f7fa;

    padding: 20px;

}

.container {

    max-width: 700px;

    margin: auto;

}

.card {

    background: white;

    padding: 25px;

    border-radius: 18px;

    box-shadow:
        0 8px 25px
        rgba(0, 100, 150, 0.08);

}

input,
textarea {

    width: 100%;

    box-sizing: border-box;

    padding: 15px;

    margin: 8px 0 18px;

    border:
        1px solid #ddd;

    border-radius: 10px;

    font-size: 16px;

}

textarea {

    min-height: 160px;

}

button {

    width: 100%;

    padding: 16px;

    border: 0;

    border-radius: 11px;

    background:
        linear-gradient(
            135deg,
            #009fe3,
            #0077ff
        );

    color: white;

    font-size: 16px;

    font-weight: 900;

}

img {

    width: 100%;

    max-height: 350px;

    object-fit: cover;

    border-radius: 13px;

    margin-bottom: 20px;

}

.back {

    display: inline-block;

    margin-top: 15px;

    text-decoration: none;

    color: #008bd2;

    font-weight: bold;

}

</style>

</head>


<body>

<div class="container">

<div class="card">

<h1>
    Post Campaign
</h1>


<p>

The image uploaded here will appear at the
very top of the public website.

Your heading and text will appear directly
under the image.

</p>


{% if campaign['image'] %}

<img
    src="{{ url_for(
        'uploaded_file',
        filename=campaign['image']
    ) }}"
>

{% endif %}


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
    placeholder="Enter your heading"
>


<label>
    Text
</label>


<textarea
    name="message"
    placeholder="Enter your promotional text"
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
    Image
</label>


<input
    type="file"
    name="image"
    accept=".jpg,.jpeg,.png,.webp"
>


<button type="submit">

    PUBLISH CAMPAIGN

</button>


</form>


<a
    class="back"
    href="{{ url_for('admin_dashboard') }}"
>
    ← Back to Dashboard
</a>


</div>

</div>

</body>

</html>

"""


@app.route(
    "/secret-admin/edit",
    methods=["GET", "POST"]
)
@admin_required
def edit_campaign():

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


        image = request.files.get(
            "image"
        )


        current_image = campaign["image"]


        # ------------------------------------------
        # IMAGE
        # ------------------------------------------

        if image and image.filename:

            if not allowed_file(
                image.filename
            ):

                flash(
                    "Invalid image format."
                )

                return redirect(
                    url_for(
                        "edit_campaign"
                    )
                )


            original_name = secure_filename(
                image.filename
            )


            extension = original_name.rsplit(
                ".",
                1
            )[1].lower()


            filename = (
                secrets.token_hex(10)
                + "."
                + extension
            )


            image.save(
                os.path.join(
                    app.config["UPLOAD_FOLDER"],
                    filename
                )
            )


            current_image = filename


        # ------------------------------------------
        # SAVE
        # ------------------------------------------

        conn = get_db()


        conn.execute(
            """
            UPDATE campaign

            SET heading = ?,
                message = ?,
                referral_target = ?,
                image = ?

            WHERE id = 1
            """,
            (
                heading,
                message,
                int(referral_target),
                current_image
            )
        )


        conn.commit()

        conn.close()


        flash(
            "Campaign published successfully!"
        )


        return redirect(
            url_for(
                "admin_dashboard"
            )
        )


    return render_template_string(
        EDIT_CAMPAIGN,
        campaign=campaign
    )


# ============================================================
# ADMIN LOGOUT
# ============================================================

@app.route(
    "/secret-admin/logout"
)
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

    return "OK"


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=int(
            os.environ.get(
                "PORT",
                5000
            )
        ),
        debug=True
    )

 