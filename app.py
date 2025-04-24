import pandas as pd
from datetime import datetime, timedelta
import random
import time
import requests
import sqlite3
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder
from flask import Flask, request, jsonify
import os
import hashlib

app = Flask(__name__)

# ThingSpeak configuration
SOIL_CHANNEL_ID = "2905970"
SOIL_READ_API_KEY = "41R500B0CY37KF7B"
SOIL_THINGSPEAK_URL = f"https://api.thingspeak.com/channels/{SOIL_CHANNEL_ID}/feeds.json?api_key={SOIL_READ_API_KEY}&results=10"

MOTOR_CHANNEL_ID = "2916541"
MOTOR_READ_API_KEY = "CBTANP5HNT77GXXP"
MOTOR_THINGSPEAK_URL = f"https://api.thingspeak.com/channels/{MOTOR_CHANNEL_ID}/feeds.json?api_key={MOTOR_READ_API_KEY}&results=10"

# Water requirements (L/acre/day)
WATER_REQUIREMENTS = {
    "Tomato": 5000,
    "Potato": 3500,
    "Lettuce": 4000,
    "Carrot": 2500,
    "Green Chilli": 3560,
    "Sugarcane": 6000,
    "Paddy": 5500
}

# Load datasets
try:
    soil_types_df = pd.read_csv("soil_types.csv")
    soil_crops_df = pd.read_csv("soil_crops.csv")
    soil_nutrients_df = pd.read_csv("soil_nutrients.csv")
    crop_nutrients_df = pd.read_csv("crop_nutrients.csv")
except FileNotFoundError as e:
    print(f"Error: CSV files not found - {e}")
    exit(1)

# SQLite setup
def init_db():
    conn = sqlite3.connect('farm.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS farmers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        email TEXT UNIQUE,
        password TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS farm_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        farmer_id INTEGER,
        location TEXT,
        land_size REAL,
        soil_option TEXT,
        soil_type TEXT,
        r INTEGER,
        g INTEGER,
        b INTEGER,
        ph REAL,
        ec REAL,
        start_date TEXT,
        water_available REAL,
        selected_crop TEXT,
        created_at TEXT,
        FOREIGN KEY (farmer_id) REFERENCES farmers (id)
    )''')
    conn.commit()
    conn.close()

init_db()

# Fetch soil moisture
def fetch_thingspeak_moisture():
    try:
        response = requests.get(SOIL_THINGSPEAK_URL, timeout=10)
        if response.status_code != 200:
            return "N/A", 0
        data = response.json()
        feeds = data.get("feeds", [])
        if not feeds:
            return "N/A", 0
        for feed in reversed(feeds):
            moisture_percent = feed.get("field4")
            if moisture_percent is not None:
                moisture_percent = float(moisture_percent)
                if 0 <= moisture_percent <= 25:
                    return "Low", moisture_percent
                elif 26 <= moisture_percent <= 50:
                    return "Moderate", moisture_percent
                elif 51 <= moisture_percent <= 75:
                    return "High", moisture_percent
                else:
                    return "Very High", moisture_percent
        return "N/A", 0
    except requests.RequestException:
        return "N/A", 0

# Fetch motor status
def fetch_motor_status():
    try:
        response = requests.get(MOTOR_THINGSPEAK_URL, timeout=10)
        if response.status_code != 200:
            return "OFF", None
        data = response.json()
        feeds = data.get("feeds", [])
        if not feeds:
            return "OFF", None
        for feed in reversed(feeds):
            motor_status = feed.get("field1")
            if motor_status is not None:
                status = "ON" if motor_status in ["1", "ON"] else "OFF"
                return status, datetime.strptime(feed["created_at"], "%Y-%m-%dT%H:%M:%SZ") if status == "ON" else None
        return "OFF", None
    except requests.RequestException:
        return "OFF", None

# Calculate water supplied
def calculate_water_supplied(crop, land_size, soil_type, start_time):
    water_req_per_acre = WATER_REQUIREMENTS.get(crop, 5500)
    total_water_needed = water_req_per_acre * land_size
    if "Sandy" in soil_type:
        total_water_needed *= 1.2
    elif "Black" in soil_type or "Clay" in soil_type:
        total_water_needed *= 0.8
    drip_rate = total_water_needed / 60
    if start_time:
        elapsed = (datetime.utcnow() - start_time).total_seconds() / 60
        return min(drip_rate * elapsed, total_water_needed)
    return 0

# Prepare training data
def prepare_training_data():
    data = []
    labels = []
    valid_crops = set(soil_crops_df["Suitable Crop"]).intersection(set(crop_nutrients_df["Crop"]))
    moisture_levels = ["Low", "Moderate", "High", "Very High"]
    for _, soil_row in soil_types_df.iterrows():
        soil_type = soil_row["Main Soil Type"] + (" - " + soil_row["Subtype"] if pd.notna(soil_row["Subtype"]) else "")
        crops = soil_crops_df[soil_crops_df["Soil Type"].str.contains(soil_type.split(" - ")[0])]["Suitable Crop"].unique()
        for crop in crops:
            if crop in valid_crops:
                nutrient_qty = float(crop_nutrients_df[crop_nutrients_df["Crop"] == crop]["Quantity (kg/acre)"].iloc[0].split()[0])
                for land_size in [0.5, 1, 2, 5, 10]:
                    for month in range(1, 13):
                        for moisture in moisture_levels:
                            water_available = random.randint(50, 20000)
                            data.append([soil_row["R"], soil_row["G"], soil_row["B"], soil_row["pH"], soil_row["EC"],
                                         moisture, water_available, land_size, month, nutrient_qty])
                            labels.append(crop)
    return pd.DataFrame(data, columns=["R", "G", "B", "pH", "EC", "Moisture", "Water_Available", "Land_Size", "Month", "Nutrient_Qty"]), labels

# Train model
le_moisture = LabelEncoder()
le_y = LabelEncoder()
model = None
try:
    X, y = prepare_training_data()
    X["Moisture"] = le_moisture.fit_transform(X["Moisture"])
    y = le_y.fit_transform(y)
    model = RandomForestClassifier(n_estimators=300, max_depth=15, random_state=42)
    model.fit(X, y)
    print("Model trained successfully.")
except Exception as e:
    print(f"Error training model: {e}")
    model = RandomForestClassifier(n_estimators=1)

# Determine soil type
def determine_soil_type(r, g, b, ph, ec, moisture):
    soil_match = soil_types_df[
        (soil_types_df["R"].between(r-5, r+5)) &
        (soil_types_df["G"].between(g-5, g+5)) &
        (soil_types_df["B"].between(b-5, b+5)) &
        (soil_types_df["pH"].between(ph-0.2, ph+0.2)) &
        (soil_types_df["EC"].between(ec-0.05, ec+0.05)) &
        (soil_types_df["Moisture Level"] == moisture)
    ]
    if not soil_match.empty:
        row = soil_match.iloc[0]
        return row["Main Soil Type"] + (" - " + row["Subtype"] if pd.notna(row["Subtype"]) else "")
    return "Unknown"

# Get crop recommendations
def get_crop_recommendations(location, water_available, soil_option, start_date, sensor_data, land_size):
    start_date_obj = datetime.strptime(start_date, "%Y-%m-%d")
    month = start_date_obj.month
    possible_crops = soil_crops_df["Suitable Crop"].unique()
    moisture, _ = fetch_thingspeak_moisture()
    
    if soil_option == "manual":
        soil_type = sensor_data["soil_type"]
        avg_soil = soil_types_df[soil_types_df["Main Soil Type"] == soil_type.split(" - ")[0]].mean(numeric_only=True)
        r, g, b, ph, ec = avg_soil[["R", "G", "B", "pH", "EC"]]
        nutrient_qty = float(crop_nutrients_df[crop_nutrients_df["Crop"].isin(possible_crops)].iloc[0]["Quantity (kg/acre)"].split()[0])
        input_data = pd.DataFrame([[r, g, b, ph, ec, le_moisture.transform([moisture])[0] if moisture else 0, water_available, land_size, month, nutrient_qty]],
                                  columns=["R", "G", "B", "pH", "EC", "Moisture", "Water_Available", "Land_Size", "Month", "Nutrient_Qty"])
    else:
        r, g, b, ph, ec = sensor_data
        soil_type = determine_soil_type(r, g, b, ph, ec, moisture)
        nutrient_qty = float(crop_nutrients_df[crop_nutrients_df["Crop"].isin(possible_crops)].iloc[0]["Quantity (kg/acre)"].split()[0])
        input_data = pd.DataFrame([[r, g, b, ph, ec, le_moisture.transform([moisture])[0], water_available, land_size, month, nutrient_qty]],
                                  columns=["R", "G", "B", "pH", "EC", "Moisture", "Water_Available", "Land_Size", "Month", "Nutrient_Qty"])
    
    preds = model.predict(input_data)
    recommended_crops = le_y.inverse_transform(preds)
    final_crops = list(set([crop for crop in recommended_crops if crop in possible_crops]))[:3]
    recommendations = []
    for crop in final_crops:
        water_req = WATER_REQUIREMENTS.get(crop, 4000)
        recommendations.append({
            "Crop": crop,
            "Estimated Cost (per acre)": water_req * 10,
            "Estimated Yield (kg/acre)": random.randint(1000, 3000),
            "Market Trend (0-1)": random.uniform(0.6, 0.9),
            "Water Requirement (L/acre/day)": water_req,
            "Nutrient Qty (kg/acre)": float(crop_nutrients_df[crop_nutrients_df["Crop"] == crop]["Quantity (kg/acre)"].iloc[0].split()[0]) if crop in crop_nutrients_df["Crop"].values else 0
        })
    return recommendations, soil_type

# Generate watering schedule
def generate_watering_schedule(crop, soil_type, land_size, start_date):
    water_req_per_acre = WATER_REQUIREMENTS.get(crop, 5500)
    total_water_needed = water_req_per_acre * land_size
    if "Sandy" in soil_type:
        total_water_needed *= 1.2
    elif "Black" in soil_type or "Clay" in soil_type:
        total_water_needed *= 0.8
    drip_rate = total_water_needed / 60
    duration_min = total_water_needed / drip_rate
    schedule = []
    start_date_obj = datetime.strptime(start_date, "%Y-%m-%d")
    for i in range(7):
        day = start_date_obj + timedelta(days=i)
        schedule.append({
            "Day": day.strftime("%Y-%m-%d"),
            "Time": "08:00 AM",
            "Water Quantity (L)": round(total_water_needed, 2),
            "Method": "Drip Irrigation",
            "Speed": f"Slow ({drip_rate:.2f} L/min)",
            "Duration (min)": round(duration_min, 2)
        })
    return schedule

# API Routes
@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    name = data.get('name')
    email = data.get('email')
    password = hashlib.sha256(data.get('password').encode()).hexdigest()
    conn = sqlite3.connect('farm.db')
    c = conn.cursor()
    try:
        c.execute("INSERT INTO farmers (name, email, password) VALUES (?, ?, ?)", (name, email, password))
        conn.commit()
        return jsonify({"success": True})
    except sqlite3.IntegrityError:
        return jsonify({"success": False, "message": "Email already exists"})
    finally:
        conn.close()

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    email = data.get('email')
    password = hashlib.sha256(data.get('password').encode()).hexdigest()
    conn = sqlite3.connect('farm.db')
    c = conn.cursor()
    c.execute("SELECT * FROM farmers WHERE email = ? AND password = ?", (email, password))
    user = c.fetchone()
    conn.close()
    return jsonify({"success": user is not None})

@app.route('/api/recommend', methods=['POST'])
def recommend():
    data = request.json
    location = data.get('location')
    land_size = float(data.get('landSize'))
    soil_option = data.get('soilOption')
    soil_type = data.get('soilType')
    start_date = data.get('startDate')
    water_available = float(data.get('waterAvailable'))
    sensor_data = {
        "soil_type": soil_type,
        "r": int(data.get('r', 0)),
        "g": int(data.get('g', 0)),
        "b": int(data.get('b', 0)),
        "ph": float(data.get('ph', 0)),
        "ec": float(data.get('ec', 0))
    }
    
    recommendations, detected_soil_type = get_crop_recommendations(location, water_available, soil_option, start_date, sensor_data, land_size)
    selected_crop = recommendations[0]["Crop"] if recommendations else "Paddy"
    schedule = generate_watering_schedule(selected_crop, detected_soil_type, land_size, start_date)
    
    # Store data
    conn = sqlite3.connect('farm.db')
    c = conn.cursor()
    c.execute("SELECT id FROM farmers WHERE email = ?", (request.json.get('email', 'test@example.com'),))
    farmer_id = c.fetchone()[0] if c.fetchone() else 1
    c.execute('''INSERT INTO farm_data (farmer_id, location, land_size, soil_option, soil_type, r, g, b, ph, ec, start_date, water_available, selected_crop, created_at)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                 (farmer_id, location, land_size, soil_option, detected_soil_type, sensor_data["r"], sensor_data["g"], sensor_data["b"],
                  sensor_data["ph"], sensor_data["ec"], start_date, water_available, selected_crop, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()
    
    return jsonify({
        "recommendations": recommendations,
        "schedule": schedule,
        "selectedCrop": selected_crop
    })

@app.route('/api/monitor', methods=['GET'])
def monitor():
    moisture, _ = fetch_thingspeak_moisture()
    motor_status, start_time = fetch_motor_status()
    water_supplied = calculate_water_supplied("Paddy", 2, "Coastal Alluvial", start_time) if motor_status == "ON" else 0
    return jsonify({
        "moisture": moisture,
        "motorStatus": motor_status,
        "waterSupplied": water_supplied
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
