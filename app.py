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

# Serve frontend
@app.route('/')
def serve_index():
    try:
        return send_from_directory('static', 'index.html')
    except Exception as e:
        logger.error(f"Error serving index.html: {e}")
        return jsonify({"error": "Failed to load frontend"}), 500

# Register endpoint
@app.route('/api/register', methods=['POST'])
def register():
    try:
        data = request.get_json()
        name = data['name']
        email = data['email']
        password = hashlib.sha256(data['password'].encode()).hexdigest()

        conn = sqlite3.connect('farm.db')
        c = conn.cursor()
        try:
            c.execute("INSERT INTO farmers (name, email, password) VALUES (?, ?, ?)", 
                     (name, email, password))
            conn.commit()
            return jsonify({"message": "Registration successful! Please login."}), 201
        except sqlite3.IntegrityError:
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
        email = data['email']
        password = hashlib.sha256(data['password'].encode()).hexdigest()

        conn = sqlite3.connect('farm.db')
        c = conn.cursor()
        c.execute("SELECT id, name FROM farmers WHERE email = ? AND password = ?", 
                 (email, password))
        user = c.fetchone()
        conn.close()

        if user:
            return jsonify({"message": "Login successful", "farmer_id": user[0], "name": user[1]}), 200
        return jsonify({"error": "Login failed"}), 401
    except Exception as e:
        logger.error(f"Login error: {e}")
        return jsonify({"error": "Login failed"}), 500

# Recommendation endpoint
@app.route('/api/recommend', methods=['POST'])
def recommend():
    try:
        data = request.get_json()
        logger.info(f"Received data: {data}")
        farmer_id = data['farmer_id']
        location = data['location']
        land_size = float(data['land_size'])
        soil_option = data['soil_option']
        start_date = data['start_date']
        water_available = float(data.get('water_available', 0))

        if soil_option == 'manual':
            soil_type = data['soil_type']
            logger.info(f"Manual soil type: {soil_type}")
        else:
            r, g, b = data['r'], data['g'], data['b']
            ph, ec = data['ph'], data['ec']
            soil_type = model.predict([[r, g, b, ph, ec]])[0]
            logger.info(f"Predicted soil type: {soil_type}")

        # Get suitable crops
        suitable_crops = soil_crops_df[soil_crops_df['Soil_Type'] == soil_type]['Crop'].tolist()
        logger.info(f"Suitable crops: {suitable_crops}")
        if not suitable_crops:
            logger.error("No suitable crops found for this soil type")
            return jsonify({"error": "No suitable crops found for this soil type"}), 400

        # Calculate crop characteristics
        recommendations = []
        for crop in suitable_crops[:3]:
            crop_info = crop_nutrients_df[crop_nutrients_df['Crop'] == crop]
            logger.info(f"Crop info for {crop}: {crop_info}")
            if crop_info.empty:
                logger.warning(f"No nutrient data for crop: {crop}")
                continue
            nutrients = crop_info['Quantity (kg/acre)'].iloc[0]
            water_requirement = 5500 if crop == 'Paddy' else 3000
            cost = water_requirement * 10
            yield_est = 1000 if crop == 'Paddy' else 2000
            market_trend = 0.8
            recommendations.append({
                "crop": crop,
                "nutrients": nutrients,
                "water_requirement": water_requirement,
                "cost": cost,
                "yield": yield_est,
                "market_trend": market_trend
            })
        logger.info(f"Recommendations generated: {recommendations}")

        if not recommendations:
            logger.error("No nutrient data found for suitable crops")
            return jsonify({"error": "No nutrient data found for suitable crops"}), 400

        # Generate watering schedule
        selected_crop = recommendations[0]['crop']
        base_water = recommendations[0]['water_requirement'] * land_size
        soil_adjust = {'Sandy Soil': 1.2, 'Black Cotton Soil - Deep Black Soil': 0.8}.get(soil_type, 1.0)
        total_water = base_water * soil_adjust
        schedule = []
        for i in range(7):
            date = (datetime.datetime.strptime(start_date, '%Y-%m-%d') + 
                    datetime.timedelta(days=i)).strftime('%Y-%m-%d')
            schedule.append({
                "day": date,
                "time": "08:00 AM",
                "water_quantity": round(total_water, 2),
                "method": "Drip Irrigation",
                "speed": "Slow",
                "duration": "60 min"
            })
        logger.info(f"Watering schedule generated: {schedule}")

        # Save farm data
        try:
            conn = sqlite3.connect('farm.db')
            c = conn.cursor()
            c.execute("""INSERT INTO farm_data (farmer_id, location, land_size, soil_option, 
                        soil_type, r, g, b, ph, ec, start_date, water_available, selected_crop, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                     (farmer_id, location, land_size, soil_option, soil_type,
                      data.get('r', 0), data.get('g', 0), data.get('b', 0), 
                      data.get('ph', 0), data.get('ec', 0), start_date, water_available, 
                      selected_crop, datetime.datetime.now().isoformat()))
            conn.commit()
            logger.info("Farm data saved successfully")
        except Exception as e:
            logger.error(f"Database save error: {e}")
            raise
        finally:
            conn.close()

        return jsonify({
            "recommendations": recommendations,
            "schedule": schedule,
            "soil_type": soil_type
        }), 200
    except Exception as e:
        logger.error(f"Recommendation error: {e}")
        return jsonify({"error": "Failed to generate recommendations"}), 500

# Monitoring endpoint
@app.route('/api/monitor', methods=['GET'])
def monitor():
    try:
        farmer_id = request.args.get('farmer_id')
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

        return jsonify({
            "moisture": moisture_level,
            "motor_status": "ON" if motor_status else "OFF",
            "water_supplied": water_supplied,
            "crop_stage": stage,
            "progress": progress
        }), 200
    except Exception as e:
        logger.error(f"Monitoring error: {e}")
        return jsonify({"error": "Failed to fetch monitoring data"}), 500

# Run the app
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
