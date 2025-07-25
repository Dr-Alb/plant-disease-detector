import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.utils import secure_filename
import numpy as np
from PIL import Image
import tensorflow as tf
import geocoder
from twilio.rest import Client
import openai

# ──────────────────────────────
# CONFIGURATION
# ──────────────────────────────
app = Flask(__name__)
app.secret_key = "your_secret_key_here"
UPLOAD_FOLDER = "static/uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# Twilio (Optional: Replace with your credentials)
TWILIO_SID = "your_twilio_sid"
TWILIO_TOKEN = "your_twilio_token"
TWILIO_FROM = "your_twilio_number"
openai.api_key = os.getenv("OPENAI_API_KEY")

# Load your TFLite model (to be added later)
MODEL_PATH = "model.tflite"
interpreter = tf.lite.Interpreter(model_path=MODEL_PATH)
interpreter.allocate_tensors()

# ──────────────────────────────
# DATABASE INIT
# ──────────────────────────────
def init_db():
    with sqlite3.connect("database.db") as conn:
        c = conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT,
                        email TEXT,
                        password TEXT
                    )""")
        c.execute("""CREATE TABLE IF NOT EXISTS scans (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER,
                        image_path TEXT,
                        result TEXT,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                    )""")
        c.execute("""CREATE TABLE IF NOT EXISTS alerts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER,
                        message TEXT,
                        scheduled_time TEXT,
                        is_sent INTEGER DEFAULT 0
                    )""")
        conn.commit()

init_db()

# ──────────────────────────────
# HELPERS
# ──────────────────────────────
def predict_image(image_path):
    img = Image.open(image_path).resize((224, 224))
    input_array = np.expand_dims(np.array(img) / 255.0, axis=0).astype(np.float32)

    input_index = interpreter.get_input_details()[0]["index"]
    output_index = interpreter.get_output_details()[0]["index"]

    interpreter.set_tensor(input_index, input_array)
    interpreter.invoke()
    output = interpreter.get_tensor(output_index)

    prediction = np.argmax(output)
    return f"Prediction result: {prediction}"

def get_gps_location():
    g = geocoder.ip('me')
    return g.latlng if g.ok else ["Unknown", "Unknown"]


def send_sms(to, message):
    client = Client(TWILIO_SID, TWILIO_TOKEN)
    client.messages.create(to=to, from_=TWILIO_FROM, body=message)

def send_sms(to, message):
    try:
        client = Client(TWILIO_SID, TWILIO_AUTH_TOKEN)
        client.messages.create(
            body=message,
            from_=TWILIO_PHONE,
            to=to
        )
        print(f"✅ SMS sent to {to}")
    except Exception as e:
        print(f"❌ SMS failed: {e}")


# ──────────────────────────────
# ROUTES
# ──────────────────────────────
@app.route('/')
def index():
    if "user_id" not in session:
        return redirect(url_for("login"))
    return render_template("home.html")

@app.route('/get-location')
def get_location():
    latlng = get_gps_location()
    return {"lat": latlng[0], "lng": latlng[1]}



@app.route('/login', methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        with sqlite3.connect("database.db") as conn:
            c = conn.cursor()
            c.execute("SELECT id FROM users WHERE email=? AND password=?", (email, password))
            user = c.fetchone()
            if user:
                session["user_id"] = user[0]
                return redirect(url_for("index"))
            else:
                flash("Invalid credentials")
    return render_template("login.html")

@app.route('/signup', methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form["username"]
        email = request.form["email"]
        password = request.form["password"]
        with sqlite3.connect("database.db") as conn:
            c = conn.cursor()
            c.execute("INSERT INTO users (username, email, password) VALUES (?, ?, ?)",
                      (username, email, password))
            conn.commit()
        return redirect(url_for("login"))
    return render_template("signup.html")

@app.route('/send-test-sms')
def send_test_sms():
    if "user_id" not in session:
        return redirect(url_for("login"))
    # Hardcoded for test; replace with user phone later
    send_sms("+2547XXXXXXX", "🚨 Test Alert from Disease Detector!")
    return "SMS sent!"


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route('/scan', methods=["GET", "POST"])
def scan():
    if request.method == "POST":
        file = request.files["image"]
        if file:
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            file.save(filepath)

            result = predict_image(filepath)
            user_id = session["user_id"]

            with sqlite3.connect("database.db") as conn:
                c = conn.cursor()
                c.execute("INSERT INTO scans (user_id, image_path, result) VALUES (?, ?, ?)",
                          (user_id, filepath, result))
                conn.commit()

            flash("Scan successful!")
            return redirect(url_for("recent_scans"))
    return render_template("scan.html")

@app.route('/recent-scans')
def recent_scans():
    user_id = session["user_id"]
    with sqlite3.connect("database.db") as conn:
        c = conn.cursor()
        c.execute("SELECT image_path, result, timestamp FROM scans WHERE user_id=? ORDER BY timestamp DESC LIMIT 5", (user_id,))
        scans = c.fetchall()
    return render_template("recent_scans.html", scans=scans)

@app.route('/alerts')
def alerts():
    phone = request.form["phone"]
    task = request.form["task"]
    time = request.form["time"]
    user_id = session["user_id"]
    with sqlite3.connect("database.db") as conn:
        c = conn.cursor()
        c.execute("SELECT message, scheduled_time FROM alerts WHERE user_id=? AND is_sent=0", (user_id,))
        alerts = c.fetchall()
        message = f"🌱 AgriScan Alert: You scheduled '{task}' at {time}."
    send_sms(phone, message)

    return render_template("alerts.html", alerts=alerts)

@app.route('/chat', methods=['POST'])
def chat():
    user_message = request.json.get("message")
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are AgriBot, a helpful assistant for farmers."},
                {"role": "user", "content": user_message}
            ]
        )
        answer = response.choices[0].message.content
        return {"response": answer}
    except Exception as e:
        return {"error": str(e)}, 500

@app.route('/quick-actions')
def quick_actions():
    return render_template("quick_actions.html")

@app.route('/profile')
def profile():
    return "User profile coming soon!"

# ──────────────────────────────
# RUN
# ──────────────────────────────
if __name__ == '__main__':
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
    app.run(host='0.0.0.0', port=5000)
