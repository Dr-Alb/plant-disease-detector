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
import time
import requests


# ──────────────────────────────
# CONFIGURATION
# ──────────────────────────────
app = Flask(__name__)
app.secret_key = "your_secret_key_here"
UPLOAD_FOLDER = "static/uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Twilio (Optional: Replace with your credentials)
TWILIO_SID = "your_twilio_sid"
TWILIO_TOKEN = "your_twilio_token"
TWILIO_FROM = "your_twilio_number"
openai.api_key = os.getenv("OPENAI_API_KEY")
WEATHER_API_KEY = "8c4e262af8008f51fe6b0d0565ba26fd"

# Load TFLite model
MODEL_PATH = "model.tflite"
interpreter = tf.lite.Interpreter(model_path=MODEL_PATH)
interpreter.allocate_tensors()

# Class labels and solution map
CLASS_NAMES = [
    'Apple___Apple_scab', 'Apple___Black_rot', 'Apple___Cedar_apple_rust', 'Apple___healthy',
    'Blueberry___healthy', 'Cherry_(including_sour)___Powdery_mildew', 'Cherry_(including_sour)___healthy',
    'Corn_(maize)___Cercospora_leaf_spot Gray_leaf_spot', 'Corn_(maize)___Common_rust_',
    'Corn_(maize)___Northern_Leaf_Blight', 'Corn_(maize)___healthy', 'Grape___Black_rot',
    'Grape___Esca_(Black_Measles)', 'Grape___Leaf_blight_(Isariopsis_Leaf_Spot)', 'Grape___healthy',
    'Orange___Haunglongbing_(Citrus_greening)', 'Peach___Bacterial_spot', 'Peach___healthy',
    'Pepper,_bell___Bacterial_spot', 'Pepper,_bell___healthy', 'Potato___Early_blight',
    'Potato___Late_blight', 'Potato___healthy', 'Raspberry___healthy', 'Soybean___healthy',
    'Squash___Powdery_mildew', 'Strawberry___Leaf_scorch', 'Strawberry___healthy',
    'Tomato___Bacterial_spot', 'Tomato___Early_blight', 'Tomato___Late_blight',
    'Tomato___Leaf_Mold', 'Tomato___Septoria_leaf_spot', 'Tomato___Spider_mites Two-spotted_spider_mite',
    'Tomato___Target_Spot', 'Tomato___Tomato_Yellow_Leaf_Curl_Virus', 'Tomato___Tomato_mosaic_virus',
    'Tomato___healthy'
]

SOLUTION_MAP = {
    
   "Apple___Apple_scab": {
        "description": "Apple scab is a fungal disease that causes dark, scabby lesions on leaves and fruit.",
        "treatment": "Apply fungicides during the early growing season and remove fallen leaves."
    },
    "Apple___Black_rot": {
        "description": "Black rot affects apples, causing cankers on limbs and rotting of fruit.",
        "treatment": "Prune affected branches, remove mummified fruits, and apply fungicide sprays."
    },
    "Apple___Cedar_apple_rust": {
        "description": "Cedar apple rust is a fungal disease requiring both apple and cedar trees to complete its lifecycle.",
        "treatment": "Remove nearby cedar trees and apply fungicides in early spring."
    },
    "Apple___healthy": {
        "description": "The plant is healthy.",
        "treatment": "No action needed."
    },
    "Blueberry___healthy": {
        "description": "The plant is healthy.",
        "treatment": "No action needed."
    },
    "Cherry_(including_sour)___Powdery_mildew": {
        "description": "Powdery mildew causes a white, powdery growth on leaves, reducing fruit quality.",
        "treatment": "Use sulfur-based fungicides and prune for better air circulation."
    },
    "Cherry_(including_sour)___healthy": {
        "description": "The plant is healthy.",
        "treatment": "No action needed."
    },
    "Corn_(maize)___Cercospora_leaf_spot Gray_leaf_spot": {
        "description": "A fungal disease causing grayish lesions on leaves, reducing photosynthesis.",
        "treatment": "Rotate crops, use resistant varieties, and apply fungicides."
    },
    "Corn_(maize)___Common_rust_": {
        "description": "Common rust appears as reddish-brown pustules on leaves.",
        "treatment": "Use resistant hybrids and fungicides if infection is severe."
    },
    "Corn_(maize)___Northern_Leaf_Blight": {
        "description": "Causes elongated gray-green lesions, leading to yield loss.",
        "treatment": "Use resistant varieties and fungicides."
    },
    "Corn_(maize)___healthy": {
        "description": "The plant is healthy.",
        "treatment": "No action needed."
    },
    "Grape___Black_rot": {
        "description": "Black rot causes black spots on leaves and rots the fruit.",
        "treatment": "Remove infected parts and apply fungicides regularly."
    },
    "Grape___Esca_(Black_Measles)": {
        "description": "A fungal disease that leads to leaf scorch and internal wood rot.",
        "treatment": "Prune infected canes and avoid excessive vine stress."
    },
    "Grape___Leaf_blight_(Isariopsis_Leaf_Spot)": {
        "description": "Small dark spots on leaves that merge into larger blighted areas.",
        "treatment": "Remove infected leaves and apply protective fungicides."
    },
    "Grape___healthy": {
        "description": "The plant is healthy.",
        "treatment": "No action needed."
    },
    "Orange___Haunglongbing_(Citrus_greening)": {
        "description": "A deadly bacterial disease spread by psyllids, causing yellow shoots and bitter fruit.",
        "treatment": "No cure. Control insect vector and remove infected trees."
    },
    "Peach___Bacterial_spot": {
        "description": "Causes dark lesions on leaves and sunken spots on fruits.",
        "treatment": "Use copper-based sprays and disease-resistant varieties."
    },
    "Peach___healthy": {
        "description": "The plant is healthy.",
        "treatment": "No action needed."
    },
    "Pepper,_bell___Bacterial_spot": {
        "description": "Bacterial infection that creates dark water-soaked spots on leaves and fruits.",
        "treatment": "Use certified seed and copper-based bactericides."
    },
    "Pepper,_bell___healthy": {
        "description": "The plant is healthy.",
        "treatment": "No action needed."
    },
    "Potato___Early_blight": {
        "description": "Dark concentric spots appear on leaves, leading to defoliation.",
        "treatment": "Use fungicides and rotate crops."
    },
    "Potato___Late_blight": {
        "description": "Rapid browning and death of leaves; caused the Irish Potato Famine.",
        "treatment": "Apply systemic fungicides and destroy infected plants."
    },
    "Potato___healthy": {
        "description": "The plant is healthy.",
        "treatment": "No action needed."
    },
    "Raspberry___healthy": {
        "description": "The plant is healthy.",
        "treatment": "No action needed."
    },
    "Soybean___healthy": {
        "description": "The plant is healthy.",
        "treatment": "No action needed."
    },
    "Squash___Powdery_mildew": {
        "description": "White powdery fungus that reduces photosynthesis and yield.",
        "treatment": "Apply sulfur-based or neem oil sprays."
    },
    "Strawberry___Leaf_scorch": {
        "description": "Dark purple spots on leaves, causing them to wither and die.",
        "treatment": "Remove infected leaves and apply fungicides."
    },
    "Strawberry___healthy": {
        "description": "The plant is healthy.",
        "treatment": "No action needed."
    },
    "Tomato___Bacterial_spot": {
        "description": "Dark water-soaked lesions on leaves, stems, and fruits.",
        "treatment": "Use resistant seeds and copper sprays."
    },
    "Tomato___Early_blight": {
        "description": "Brown concentric rings on leaves, causing defoliation.",
        "treatment": "Use crop rotation and fungicides."
    },
    "Tomato___Late_blight": {
        "description": "Grayish spots on leaves and brown lesions on fruit.",
        "treatment": "Destroy infected plants and apply fungicides."
    },
    "Tomato___Leaf_Mold": {
        "description": "Yellowing and moldy growth on underside of leaves.",
        "treatment": "Increase airflow and apply fungicides."
    },
    "Tomato___Septoria_leaf_spot": {
        "description": "Small water-soaked circular spots that spread rapidly.",
        "treatment": "Remove infected leaves and use fungicide sprays."
    },
    "Tomato___Spider_mites Two-spotted_spider_mite": {
        "description": "Tiny mites that feed on leaves, causing yellowing and webbing.",
        "treatment": "Spray with miticides or insecticidal soap."
    },
    "Tomato___Target_Spot": {
        "description": "Dark concentric spots on leaves and stems.",
        "treatment": "Improve air circulation and use fungicides."
    },
    "Tomato___Tomato_Yellow_Leaf_Curl_Virus": {
        "description": "Leaves curl and turn yellow; plant stunts in growth.",
        "treatment": "Control whiteflies and remove infected plants."
    },
    "Tomato___Tomato_mosaic_virus": {
        "description": "Mosaic pattern on leaves and stunted growth.",
        "treatment": "Remove infected plants and disinfect tools."
    },
    "Tomato___healthy": {
        "description": "The plant is healthy.",
        "treatment": "No action needed."
    }
}

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

    prediction_idx = int(np.argmax(output))
    confidence = float(np.max(output))  #  Confidence score
    class_name = CLASS_NAMES[prediction_idx]

    # Extract plant type from label (before the "___")
    plant_type = class_name.split("___")[0]

    #  Error handling: Low confidence or unknown plant
    if confidence < 0.70:  # Threshold can be adjusted
        raise ValueError(" Unable to confidently identify this plant. Please upload a clearer leaf image.")

    #  Error handling: Unsupported plant type
    supported_plants = set([label.split("___")[0] for label in CLASS_NAMES])
    if plant_type not in supported_plants:
        raise ValueError(f" This plant type ('{plant_type}') is not supported by the model.")

    solution = SOLUTION_MAP.get(class_name, {"description": "No info", "treatment": "No solution available."})

    return {
        "name": class_name,
        "plant": plant_type,
        "confidence": round(confidence * 100, 2),
        "solution": solution
    }


def get_weather(lat, lon):
    try:
        url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={WEATHER_API_KEY}&units=metric"
        response = requests.get(url)
        data = response.json()
        if data.get("main"):
            return {
                "location": data["name"],
                "temperature": data["main"]["temp"],
                "condition": data["weather"][0]["description"].capitalize()
            }
        else:
            return {"location": "Unknown", "temperature": "?", "condition": "Unavailable"}
    except:
        return {"location": "Unknown", "temperature": "?", "condition": "Unavailable"}

def get_gps_location():
    g = geocoder.ip('me')
    return g.latlng if g.ok else ["Unknown", "Unknown"]

def send_sms(to, message):
    try:
        client = Client(TWILIO_SID, TWILIO_TOKEN)
        client.messages.create(
            body=message,
            from_=TWILIO_FROM,
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

    # Fetch user profile info
    with sqlite3.connect("database.db") as conn:
        c = conn.cursor()
        c.execute("SELECT username, email FROM users WHERE id = ?", (session["user_id"],))
        user = c.fetchone()
        if user:
            username, email = user
        else:
            username = email = "Unknown"

    # Get location and weather
    latlng = get_gps_location()
    weather = get_weather(latlng[0], latlng[1])

    # Fetch recent scans – 
    with sqlite3.connect("database.db") as conn:
        c = conn.cursor()
        c.execute("""
            SELECT image_path, disease_name AS result, solution, timestamp 
            FROM scans 
            WHERE user_id=? 
            ORDER BY timestamp DESC 
            LIMIT 5
        """, (session["user_id"],))
        scans = c.fetchall()

    # Fetch active alerts – 
    with sqlite3.connect("database.db") as conn:
        c = conn.cursor()
        c.execute("""
            SELECT task AS message, alert_time AS scheduled_time 
            FROM alerts 
            WHERE user_id=?
        """, (session["user_id"],))
        alerts = c.fetchall()

    return render_template("home.html", scans=scans, alerts=alerts, weather=weather)

@app.route('/profile')
def profile():
    return render_template("profile.html")


@app.route('/get-location')
def get_location():
    latlng = get_gps_location()
    return {"lat": latlng[0], "lng": latlng[1]}

@app.route('/login', methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get('email')
        password = request.form.get('password')
        with sqlite3.connect("database.db") as conn:
            c = conn.cursor()
            c.execute("SELECT id, username FROM users WHERE email=? AND password=?", (email, password))

            user = c.fetchone()
            if user:
                session["user_id"] = user[0]
                session["username"] = user[1]
                session["email"] = email
                flash("Login successful!")
                return redirect(url_for("index"))
            else:
                flash("Invalid credentials")
    return render_template("login.html")

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form['password']
        phone = request.form.get('phone_number') 

        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        try:
            cursor.execute('INSERT INTO users (username, email, password, phone_number) VALUES (?, ?, ?, ?)',
                      (username, email, password, phone))
            conn.commit()
            flash('Signup successful. Please log in.')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Email already exists.')
        finally:
            conn.close()
    return render_template('signup.html')

@app.route('/send-test-sms')
def send_test_sms():
    if "user_id" not in session:
        return redirect(url_for("login"))
    send_sms("+2547XXXXXXX", "🚨 Test Alert from Disease Detector!")
    return "SMS sent!"

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route('/scan', methods=['GET', 'POST'])
def scan():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        try:
            print("DEBUG: Scan request started")

            # Handle file upload
            file = request.files.get('image')
            if not file or file.filename == "":
                print("ERROR: No image uploaded")
                flash("Please upload or capture a photo")
                return redirect(url_for('scan'))

            filename = f"{int(time.time())}_{file.filename}"
            filepath = os.path.join("static/uploads", filename)
            file.save(filepath)
            print(f"DEBUG: File saved at {filepath}")

            # Make prediction
            disease_info = predict_image(filepath)
        
            print(f"DEBUG: Prediction result: {disease_info}")

            # Get GPS/location 
            location = request.form.get('location', 'Unknown')
            print(f"DEBUG: Location: {location}")

            # Get user details
            user_id = session['user_id']
            conn = sqlite3.connect('database.db')
            cursor = conn.cursor()
            cursor.execute("SELECT phone_number FROM users WHERE id = ?", (user_id,))
            phone_result = cursor.fetchone()
            phone = phone_result[0] if phone_result else None
            print(f"DEBUG: User phone: {phone}")

            # Store scan in database
            cursor.execute(
                "INSERT INTO scans (user_id, image_path, disease_name, solution) VALUES (?, ?, ?, ?)",
                (user_id, filepath, disease_info["name"], disease_info["solution"]["treatment"])
            )
            conn.commit()
            print("DEBUG: Scan inserted into database")
            conn.close()
            return jsonify({
                "image": f"/{filepath}",
            "disease": disease_info["name"],
            "plant": disease_info["plant"],
            "confidence": f"{disease_info['confidence']}%",
            "solution": disease_info["solution"]["treatment"]
               }
        except ValueError as e:
            return {"error": str(e)}, 400  )

            # Send SMS alert
            if phone:
                message = f"🌿 Disease Detected: {disease_info['name']}\n💡 Solution: {disease_info['solution']['treatment']}"
                send_sms(phone, message)
                print("DEBUG: SMS sent")

            # Return result page
            return render_template("scan.html",
                image_file=filename,
                disease=disease_info["name"],
                solution=disease_info["solution"]
            )

        except Exception as e:
            print(" ERROR in /scan:", str(e))
            return f"Internal Server Error: {str(e)}", 500

    return render_template("scan.html")


@app.route('/recent-scans')
def recent_scans():
    user_id = session["user_id"]
    with sqlite3.connect("database.db") as conn:
        c = conn.cursor()
        c.execute("SELECT image_path, disease_name AS result, solution, timestamp FROM scans WHERE user_id=? ORDER BY timestamp DESC LIMIT 5", (session["user_id"],))

        scans = c.fetchall()
    return render_template("recent_scans.html", scans=scans)

@app.route('/alerts', methods=["GET", "POST"])
def alerts():
    if request.method == "POST":
        phone = request.form["phone"]
        task = request.form["task"]
        time = request.form["time"]
        user_id = session["user_id"]

        message = f"🌱 AgriScan Alert: You scheduled '{task}' at {time}."
        with sqlite3.connect("database.db") as conn:
            c = conn.cursor()
            c.execute("INSERT INTO alerts (user_id, message, scheduled_time) VALUES (?, ?, ?)",
                      (user_id, message, time))
            conn.commit()

        send_sms(phone, message)

    user_id = session["user_id"]
    with sqlite3.connect("database.db") as conn:
        c = conn.cursor()
        c.execute("SELECT message, scheduled_time FROM alerts WHERE user_id=? AND is_sent=0", (user_id,))
        alerts = c.fetchall()

    return render_template("alerts.html", alerts=alerts)

@app.route('/favicon.ico')
def favicon():
    return '', 204


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



# ──────────────────────────────
# RUN
# ──────────────────────────────
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))  
    app.run(host='0.0.0.0', port=port)
