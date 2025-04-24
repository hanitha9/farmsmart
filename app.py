from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import sqlite3
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
import requests
import os
import hashlib
import datetime
import logging
import numpy as np
import random

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# SQLite database initialization
def init_db():
    try:
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
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
    finally:
        conn.close()

init_db()

# Load CSV files with validation
try:
    soil_types_df = pd.read_csv('soil_types.csv')
    soil_crops_df = pd.read_csv('soil_crops.csv')
    soil_nutrients_df = pd.read_csv('soil_nutrients.csv')
    crop_nutrients_df = pd.read_csv('crop_nutrients.csv')

    # Validate soil_types.csv
    required_soil_types_cols = ['soil_type', 'r', 'g', 'b', 'ph', 'ec']
    missing_soil_types_cols = [col for col in required_soil_types_cols if col not in soil_types_df.columns]
    if missing_soil_types_cols:
        logger.error(f"Missing columns in soil_types.csv: {missing_soil_types_cols}")
        raise ValueError(f"Missing columns in soil_types.csv: {missing_soil_types_cols}")

    # Validate soil_crops.csv
    required_soil_crops_cols = ['Soil_Type', 'Crop']
    missing_soil_crops_cols = [col for col in required_soil_crops_cols if col not in soil_crops_df.columns]
    if missing_soil_crops_cols:
        logger.error(f"Missing columns in soil_crops.csv: {missing_soil_crops_cols}")
        raise ValueError(f"Missing columns in soil_crops.csv: {missing_soil_crops_cols}")

    # Validate crop_nutrients.csv
    required_crop_nutrients_cols = ['Crop', 'Quantity (kg/acre)']
    missing_crop_nutrients_cols = [col for col in required_crop_nutrients_cols if col not in crop_nutrients_df.columns]
    if missing_crop_nutrients_cols:
        logger.error(f"Missing columns in crop_nutrients.csv: {missing_crop_nutrients_cols}")
        raise ValueError(f"Missing columns in crop_nutrients.csv: {missing_crop_nutrients_cols}")

    logger.info("CSV files loaded successfully")
except Exception as e:
    logger.error(f"Failed to load CSV files: {e}")
    raise

# Train RandomForest model
features = ['r', 'g', 'b', 'ph', 'ec']
X = soil_types_df[features]
y = soil_types_df['soil_type']
model = RandomForestClassifier(n_estimators=100, max_depth=15, random_state=42)
model.fit(X, y)
logger.info("RandomForest model trained successfully")

# ThingSpeak API configuration
SOIL_THINGSPEAK_URL = "https://api.thingspeak.com/channels/2905970/feeds.json?api_key=41R500B0CY37KF7B&results=10"
MOTOR_THINGSPEAK_URL = "https://api.thingspeak.com/channels/2916541/feeds.json?api_key=CBTANP5HNT77GXXP&results=10"

# Crop image URLs (improved with valid placeholders)
crop_images = {
    "Paddy": "https://images.unsplash.com/photo-1592982538443-2e5b5f6b5d5e",
    "Tomato": "https://images.unsplash.com/photo-1598033129183-8b9a6b9b9b9b",
    "Brinjal": "https://images.unsplash.com/photo-1605727202208-9469b9b9b9b9",
    "Okra": "https://images.unsplash.com/photo-1627309368969-9b9b9b9b9b9b",
    "Coconut": "https://images.unsplash.com/photo-1604537529428-15bc4e9b9b9b",
    "Banana": "https://images.unsplash.com/photo-1571771894821-ce9b6c0b216e",
    "Sugarcane": "https://images.unsplash.com/photo-1611080626919-7cf5a9b9b9b9",
    "Pumpkin": "https://images.unsplash.com/photo-1509398562749-9b9b9b9b9b9b"
}

# Serve frontend
@app.route('/')
def serve_index():
    try:
        logger.info("Serving index.html")
        return send_from_directory('static', 'index.html')
    except Exception as e:
        logger.error(f"Error serving index.html: {e}")
        return jsonify({"error": "Failed to load frontend"}), 500

# Register endpoint
@app.route('/api/register', methods=['POST'])
def register():
    try:
        data = request.get_json()
        logger.info(f"Register data: {data}")
        name = data['name']
        email = data['email']
        password = hashlib.sha256(data['password'].encode()).hexdigest()

        conn = sqlite3.connect('farm.db')
        c = conn.cursor()
        try:
            c.execute("INSERT INTO farmers (name, email, password) VALUES (?, ?, ?)", 
                     (name, email, password))
            conn.commit()
            logger.info("User registered successfully")
            return jsonify({"message": "Registration successful! Please login."}), 201
        except sqlite3.IntegrityError:
            logger.error("Email already exists")
            return jsonify({"error": "Email already exists"}), 400
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"Registration error: {e}")
        return jsonify({"error": "Registration failed"}), 500

# Login endpoint
@app.route('/api/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        logger.info(f"Login data: {data}")
        email = data['email']
        password = hashlib.sha256(data['password'].encode()).hexdigest()

        conn = sqlite3.connect('farm.db')
        c = conn.cursor()
        c.execute("SELECT id, name FROM farmers WHERE email = ? AND password = ?", 
                 (email, password))
        user = c.fetchone()
        conn.close()

        if user:
            logger.info(f"Login successful for user ID: {user[0]}")
            return jsonify({"message": "Login successful", "farmer_id": user[0], "name": user[1]}), 200
        logger.error("Login failed: Invalid credentials")
        return jsonify({"error": "Login failed"}), 401
    except Exception as e:
        logger.error(f"Login error: {e}")
        return jsonify({"error": "Login failed"}), 500

# Recommendation endpoint
@app.route('/api/recommend', methods=['POST'])
def recommend():
    try:
        data = request.get_json()
        if not data:
            logger.error("No JSON data received")
            return jsonify({"error": "Invalid request data"}), 400

        logger.info(f"Received data: {data}")
        if 'farmer_id' not in data:
            logger.error("Missing farmer_id")
            return jsonify({"error": "Farmer ID is required"}), 400
        farmer_id = data['farmer_id']

        location = data.get('location', '')
        land_size = float(data.get('land_size', 0))
        soil_option = data.get('soil_option', '')
        start_date = data.get('start_date', '')
        water_available = float(data.get('water_available', 0))

        if not location or land_size <= 0 or not soil_option or not start_date:
            logger.error("Invalid input data")
            return jsonify({"error": "All required fields must be provided and valid"}), 400

        if soil_option == 'manual':
            if 'soil_type' not in data:
                logger.error("Missing soil_type for manual option")
                return jsonify({"error": "Soil type is required for manual selection"}), 400
            soil_type = data['soil_type']
            logger.info(f"Manual soil type: {soil_type}")
        else:
            if not all(k in data for k in ['r', 'g', 'b', 'ph', 'ec']):
                logger.error("Missing sensor data")
                return jsonify({"error": "Sensor data (r, g, b, ph, ec) required"}), 400
            r, g, b = data['r'], data['g'], data['b']
            ph, ec = data['ph'], data['ec']
            soil_type = model.predict([[r, g, b, ph, ec]])[0]
            logger.info(f"Predicted soil type: {soil_type}")

        # Get suitable crops, prioritize vegetables
        suitable_crops = soil_crops_df[soil_crops_df['Soil_Type'] == soil_type]['Crop'].tolist()
        logger.info(f"Suitable crops: {suitable_crops}")
        if not suitable_crops:
            logger.error("No suitable crops found for this soil type")
            return jsonify({"error": "No suitable crops found for this soil type"}), 400

        # Prioritize vegetable crops
        vegetable_crops = ['Tomato', 'Brinjal', 'Okra', 'Pumpkin']
        prioritized_crops = [crop for crop in suitable_crops if crop in vegetable_crops]
        other_crops = [crop for crop in suitable_crops if crop not in vegetable_crops]
        selected_crops = prioritized_crops[:2] + random.sample(other_crops, 1) if len(other_crops) >= 1 else prioritized_crops[:3]
        selected_crops = selected_crops[:3]  # Ensure exactly 3 crops
        if len(selected_crops) < 3:
            selected_crops.extend(random.sample(other_crops, min(3 - len(selected_crops), len(other_crops))))
        logger.info(f"Selected crops: {selected_crops}")

        # Calculate crop characteristics
        recommendations = []
        for crop in selected_crops:
            crop_info = crop_nutrients_df[crop_nutrients_df['Crop'] == crop]
            logger.info(f"Crop info for {crop}: {crop_info}")
            if crop_info.empty:
                logger.warning(f"No nutrient data for crop: {crop}")
                continue
            nutrients = int(crop_info['Quantity (kg/acre)'].iloc[0])
            water_requirement = 5500 if crop == 'Paddy' else 3000 if crop in ['Tomato', 'Brinjal', 'Okra', 'Pumpkin'] else 4000
            cost = water_requirement * 10
            yield_est = 1000 if crop == 'Paddy' else 2000 if crop in vegetable_crops else 1500
            market_trend = 0.8 if crop in vegetable_crops else 0.7
            recommendations.append({
                "crop": crop,
                "nutrients": nutrients,
                "water_requirement": water_requirement,
                "cost": cost,
                "yield": yield_est,
                "market_trend": market_trend,
                "image_url": crop_images.get(crop, "https://via.placeholder.com/150")
            })
        logger.info(f"Recommendations generated: {recommendations}")

        if not recommendations:
            logger.error("No nutrient data found for suitable crops")
            return jsonify({"error": "No nutrient data found for suitable crops"}), 400

        # Save farm data (no initial schedule)
        try:
            conn = sqlite3.connect('farm.db')
            c = conn.cursor()
            c.execute("""INSERT INTO farm_data (farmer_id, location, land_size, soil_option, 
                        soil_type, r, g, b, ph, ec, start_date, water_available, selected_crop, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                     (farmer_id, location, land_size, soil_option, soil_type,
                      data.get('r', 0), data.get('g', 0), data.get('b', 0), 
                      data.get('ph', 0), data.get('ec', 0), start_date, water_available, 
                      None, datetime.datetime.now().isoformat()))
            conn.commit()
            logger.info("Farm data saved successfully")
        except Exception as e:
            logger.error(f"Database save error: {e}")
            raise
        finally:
            conn.close()

        # Ensure JSON serializability
        for rec in recommendations:
            for key, value in rec.items():
                if isinstance(value, np.integer):
                    rec[key] = int(value)
                elif isinstance(value, np.floating):
                    rec[key] = float(value)

        return jsonify({
            "recommendations": recommendations,
            "soil_type": soil_type
        }), 200
    except Exception as e:
        logger.error(f"Recommendation error: {e}")
        return jsonify({"error": f"Failed to generate recommendations: {str(e)}"}), 500

# Schedule endpoint for selected crop
@app.route('/api/schedule', methods=['POST'])
def generate_schedule():
    try:
        data = request.get_json()
        logger.info(f"Schedule data: {data}")
        if not all(k in data for k in ['farmer_id', 'crop', 'soil_type', 'land_size', 'start_date', 'water_available']):
            logger.error("Missing required fields")
            return jsonify({"error": "All required fields must be provided"}), 400

        farmer_id = data['farmer_id']
        crop = data['crop']
        soil_type = data['soil_type']
        land_size = float(data['land_size'])
        start_date = data['start_date']
        water_available = float(data['water_available'])

        # Get crop info
        crop_info = crop_nutrients_df[crop_nutrients_df['Crop'] == crop]
        if crop_info.empty:
            logger.error(f"No nutrient data for crop: {crop}")
            return jsonify({"error": f"No nutrient data for crop: {crop}"}), 400
        nutrients = int(crop_info['Quantity (kg/acre)'].iloc[0])
        water_requirement = 5500 if crop == 'Paddy' else 3000 if crop in ['Tomato', 'Brinjal', 'Okra', 'Pumpkin'] else 4000

        # Adjust water based on soil type
        soil_adjust = {
            'Sandy Soil': 1.2,
            'Black Cotton Soil - Deep Black Soil': 0.8,
            'Coastal Alluvial': 1.0,
            'Loamy Soil': 1.0,
            'Laterite Soil': 0.9,
            'Red Sandy Loam - Fine Sandy Loam': 1.1,
            'Red Sandy Loam - Coarse Sandy Loam': 1.1,
            'Red Sandy Loam - Gravelly Sandy Loam': 1.2,
            'Black Cotton Soil - Shallow Black Soil': 0.9,
            'Black Cotton Soil - Medium Black Soil': 0.85
        }.get(soil_type, 1.0)
        total_water = water_requirement * land_size * soil_adjust

        # Generate water schedule
        water_schedule = []
        for i in range(7):
            date = (datetime.datetime.strptime(start_date, '%Y-%m-%d') + 
                    datetime.timedelta(days=i)).strftime('%Y-%m-%d')
            water_schedule.append({
                "day": date,
                "time": "08:00 AM",
                "water_quantity": round(total_water, 2),
                "method": "Drip Irrigation",
                "speed": "Slow",
                "duration": "60 min"
            })

        # Generate nutrient schedule (weekly)
        nutrient_schedule = []
        for i in range(4):  # 4 weeks
            date = (datetime.datetime.strptime(start_date, '%Y-%m-%d') + 
                    datetime.timedelta(days=i*7)).strftime('%Y-%m-%d')
            nutrient_schedule.append({
                "week_start": date,
                "nutrient_quantity": round(nutrients * land_size * 0.25, 2),  # 25% per week
                "type": "NPK Fertilizer",
                "application_method": "Soil Application"
            })

        # Organic pesticide recommendations
        pesticides = {
            "Tomato": {
                "pesticide": "Neem Oil Spray",
                "preparation": "Mix 5ml neem oil with 1L water and a drop of dish soap. Spray on leaves.",
                "measures": "Apply weekly, avoid midday heat. Monitor for pests like aphids."
            },
            "Brinjal": {
                "pesticide": "Garlic Spray",
                "preparation": "Blend 10 garlic cloves with 1L water, strain, and spray.",
                "measures": "Apply bi-weekly. Check for fruit borers."
            },
            "Okra": {
                "pesticide": "Chili-Garlic Spray",
                "preparation": "Blend 5 chilies and 5 garlic cloves with 1L water, strain, and spray.",
                "measures": "Apply weekly. Inspect for whiteflies."
            },
            "Paddy": {
                "pesticide": "Fermented Buttermilk",
                "preparation": "Mix 1L buttermilk with 9L water, ferment for 2 days, and spray.",
                "measures": "Apply every 10 days. Monitor for stem borers."
            }
        }.get(crop, {
            "pesticide": "General Neem Spray",
            "preparation": "Mix 5ml neem oil with 1L water and a drop of dish soap.",
            "measures": "Apply weekly."
        })

        # Update farm data with selected crop
        try:
            conn = sqlite3.connect('farm.db')
            c = conn.cursor()
            c.execute("UPDATE farm_data SET selected_crop = ? WHERE farmer_id = ? AND created_at = (SELECT MAX(created_at) FROM farm_data WHERE farmer_id = ?)",
                     (crop, farmer_id, farmer_id))
            conn.commit()
            logger.info(f"Updated selected crop to {crop}")
        except Exception as e:
            logger.error(f"Database update error: {e}")
            raise
        finally:
            conn.close()

        return jsonify({
            "water_schedule": water_schedule,
            "nutrient_schedule": nutrient_schedule,
            "pesticide": pesticides,
            "crop": crop,
            "soil_type": soil_type
        }), 200
    except Exception as e:
        logger.error(f"Schedule error: {e}")
        return jsonify({"error": f"Failed to generate schedule: {str(e)}"}), 500

# Monitoring endpoint
@app.route('/api/monitor', methods=['GET'])
def monitor():
    try:
        farmer_id = request.args.get('farmer_id')
        if not farmer_id:
            logger.error("Missing farmer_id for monitoring")
            return jsonify({"error": "Farmer ID is required"}), 400

        conn = sqlite3.connect('farm.db')
        c = conn.cursor()
        c.execute("SELECT start_date, selected_crop FROM farm_data WHERE farmer_id = ? ORDER BY created_at DESC LIMIT 1", 
                 (farmer_id,))
        farm_data = c.fetchone()
        conn.close()

        if not farm_data:
            return jsonify({"error": "No farm data found"}), 404

        start_date, selected_crop = farm_data
        start = datetime.datetime.strptime(start_date, '%Y-%m-%d')
        days_passed = (datetime.datetime.now() - start).days

        # Determine crop stage
        if days_passed < 30:
            stage = "Germination"
            progress = 25
        elif days_passed < 60:
            stage = "Vegetative Growth"
            progress = 50
        elif days_passed < 90:
            stage = "Flowering"
            progress = 75
        else:
            stage = "Harvesting"
            progress = 100

        # Fetch ThingSpeak data
        try:
            soil_response = requests.get(SOIL_THINGSPEAK_URL, timeout=5).json()
            motor_response = requests.get(MOTOR_THINGSPEAK_URL, timeout=5).json()

            moisture = float(soil_response['feeds'][-1]['field4']) if soil_response['feeds'] else 0
            motor_status = int(motor_response['feeds'][-1]['field1']) if motor_response['feeds'] else 0
            water_supplied = 183.33 * 60 if motor_status else 0

            moisture_level = ("Low" if moisture < 25 else "Moderate" if moisture < 50 else 
                           "High" if moisture < 75 else "Very High")
        except Exception as e:
            logger.error(f"ThingSpeak error: {e}")
            moisture_level = "N/A"
            motor_status = 0
            water_supplied = 0

        # Generate notifications
        notifications = []
        if moisture_level == "Low":
            notifications.append({"type": "warning", "message": "Soil moisture is low. Consider increasing irrigation."})
        if water_supplied == 0 and stage != "Harvesting":
            notifications.append({"type": "info", "message": "No water supplied recently. Check motor status."})

        return jsonify({
            "moisture": moisture_level,
            "motor_status": "ON" if motor_status else "OFF",
            "water_supplied": water_supplied,
            "crop_stage": stage,
            "progress": progress,
            "notifications": notifications
        }), 200
    except Exception as e:
        logger.error(f"Monitoring error: {e}")
        return jsonify({"error": "Failed to fetch monitoring data"}), 500

# Update crop stage endpoint
@app.route('/api/update_stage', methods=['POST'])
def update_stage():
    try:
        data = request.get_json()
        logger.info(f"Update stage data: {data}")
        farmer_id = data['farmer_id']
        new_stage = data['stage']
        progress = {"Germination": 25, "Vegetative Growth": 50, "Flowering": 75, "Harvesting": 100}.get(new_stage, 25)

        conn = sqlite3.connect('farm.db')
        c = conn.cursor()
        c.execute("UPDATE farm_data SET selected_crop = ?, created_at = ? WHERE farmer_id = ? AND created_at = (SELECT MAX(created_at) FROM farm_data WHERE farmer_id = ?)",
                 (f"{data['selected_crop']} ({new_stage})", datetime.datetime.now().isoformat(), farmer_id, farmer_id))
        conn.commit()
        logger.info(f"Updated crop stage to {new_stage}")
        conn.close()

        return jsonify({"message": "Crop stage updated", "stage": new_stage, "progress": progress}), 200
    except Exception as e:
        logger.error(f"Stage update error: {e}")
        return jsonify({"error": f"Failed to update stage: {str(e)}"}), 500

# Run the app
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
