from flask import Flask, request, jsonify
from flask_cors import CORS
import random
from datetime import datetime, timedelta
import requests

app = Flask(__name__, static_folder='static', static_url_path='')
CORS(app)

# Simulated database for users, farm details, and selected crops
users_db = {}
farm_details_db = {}
selected_crops_db = {}

# Crop details database
crop_details = {
    "Tomato": {
        "image_url": "https://images.unsplash.com/photo-1598516803209-7f16c7a24135?auto=format&fit=crop&w=500&q=80",
        "details": {
            "Scientific Name": "Solanum lycopersicum",
            "Growth Conditions": "Tomatoes thrive in well-drained, fertile soil with a pH of 6.0-6.8. Full sun (6-8 hours daily) and temperatures 20°C-30°C.",
            "Soil Requirements": "Loamy or sandy loam soil with good organic matter.",
            "Water Needs": "1-2 inches per week, consistent moisture.",
            "Care Tips": "Stake or cage plants, mulch to retain moisture, use 10-10-10 fertilizer.",
            "Pests and Diseases": "Aphids, whiteflies, tomato hornworms, blight. Use neem oil or copper fungicides.",
            "Harvest Time": "60-80 days after planting, when fruits are firm and colored.",
            "Yield Potential": "20-30 tons per acre under optimal conditions."
        }
    },
    "Rice": {
        "image_url": "https://images.unsplash.com/photo-1592918319975-86a7b78c5c3d?auto=format&fit=crop&w=500&q=80",
        "details": {
            "Scientific Name": "Oryza sativa",
            "Growth Conditions": "Flooded fields, clayey soil, pH 5.5-7.0, 20°C-37°C.",
            "Soil Requirements": "Clay or silty loam with good water retention.",
            "Water Needs": "2-5 cm standing water, reduce near maturity.",
            "Care Tips": "Use nitrogen-rich urea, maintain water levels, weed control.",
            "Pests and Diseases": "Stem borers, leaf folders, blast. Use neem extracts or resistant varieties.",
            "Harvest Time": "90-150 days, when grains are golden.",
            "Yield Potential": "4-6 tons per acre."
        }
    },
    "Wheat": {
        "image_url": "https://images.unsplash.com/photo-1591984472815-5b3b4b5f6c1e?auto=format&fit=crop&w=500&q=80",
        "details": {
            "Scientific Name": "Triticum aestivum",
            "Growth Conditions": "Well-drained loamy soil, pH 6.0-7.5, 15°C-25°C.",
            "Soil Requirements": "Loamy or clay-loam with good drainage.",
            "Water Needs": "4-5 irrigations, 500 mm total.",
            "Care Tips": "Sow in rows 20 cm apart, use phosphorus fertilizers.",
            "Pests and Diseases": "Aphids, rust, smut. Use resistant varieties or sprays.",
            "Harvest Time": "90-120 days, when grains are hard.",
            "Yield Potential": "2-4 tons per acre."
        }
    }
}

# Sample crop recommendations based on soil type
crop_recommendations = {
    "Coastal Alluvial": [
        {"crop": "Tomato", "nutrients": 50, "water_requirement": 600, "cost": "Low", "yield": "High", "market_trend": "Stable"},
        {"crop": "Rice", "nutrients": 70, "water_requirement": 1200, "cost": "Medium", "yield": "High", "market_trend": "Rising"},
        {"crop": "Wheat", "nutrients": 60, "water_requirement": 500, "cost": "Low", "yield": "Medium", "market_trend": "Stable"}
    ]
    # Add more soil types as needed
}

@app.route('/')
def index():
    return app.send_static_file('index.html')

@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    name = data.get('name')

    if not email or not password or not name:
        return jsonify({"error": "Missing required fields"}), 400

    if email in users_db:
        return jsonify({"error": "Email already registered"}), 400

    farmer_id = str(len(users_db) + 1)
    users_db[email] = {"farmer_id": farmer_id, "password": password, "name": name}
    return jsonify({"message": "Registration successful! Please login.", "farmer_id": farmer_id}), 200

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({"error": "Missing email or password"}), 400

    user = users_db.get(email)
    if not user or user['password'] != password:
        return jsonify({"error": "Invalid email or password"}), 401

    return jsonify({"farmer_id": user['farmer_id']}), 200

@app.route('/api/recommend', methods=['POST'])
def recommend():
    data = request.get_json()
    farmer_id = data.get('farmer_id')
    soil_option = data.get('soil_option')
    soil_type = data.get('soil_type') if soil_option == 'manual' else None

    if not farmer_id:
        return jsonify({"error": "Farmer ID required"}), 400

    farm_details_db[farmer_id] = data

    if soil_option == 'manual':
        soil_type = soil_type
    else:
        soil_type = "Coastal Alluvial"  # Simplified for demo

    recommendations = crop_recommendations.get(soil_type, [])
    for crop in recommendations:
        crop["image_url"] = crop_details.get(crop["crop"], {}).get("image_url", "https://via.placeholder.com/100")

    return jsonify({"soil_type": soil_type, "recommendations": recommendations}), 200

@app.route('/api/schedule', methods=['POST'])
def schedule():
    data = request.get_json()
    crop = data.get('crop')
    land_size = data.get('land_size')
    start_date = data.get('start_date')

    water_schedule = [
        {"day": (datetime.strptime(start_date, '%Y-%m-%d') + timedelta(days=i)).strftime('%Y-%m-%d'), "time": "08:00", "water_quantity": 500 * land_size, "method": "Drip", "speed": "Low", "duration": "1 hr"}
        for i in range(5)
    ]
    nutrient_schedule = [
        {"week_start": (datetime.strptime(start_date, '%Y-%m-%d') + timedelta(weeks=i)).strftime('%Y-%m-%d'), "nutrient_quantity": 10 * land_size, "type": "NPK 20-20-20", "application_method": "Foliar"}
        for i in range(3)
    ]
    return jsonify({"water_schedule": water_schedule, "nutrient_schedule": nutrient_schedule}), 200

@app.route('/api/monitor', methods=['GET'])
def monitor():
    farmer_id = request.args.get('farmer_id')
    if not farmer_id:
        return jsonify({"error": "Farmer ID required"}), 400

    return jsonify({
        "moisture": random.choice(["Low", "Moderate", "High"]),
        "motor_status": random.choice(["On", "Off"]),
        "water_supplied": random.randint(100, 1000),
        "notifications": [
            {"message": "Moisture level is low. Consider irrigating.", "type": "warning"}
        ]
    }), 200

@app.route('/api/update_stage', methods=['POST'])
def update_stage():
    data = request.get_json()
    stage = data.get('stage')
    progress_map = {
        "Preparation of soil": 14,
        "Sowing": 28,
        "Adding fertilizers and manures": 43,
        "Irrigation": 57,
        "Protection from weeds or pests": 71,
        "Harvesting": 86,
        "Storage of the yield": 100
    }
    progress = progress_map.get(stage, random.randint(10, 100))
    return jsonify({"stage": stage, "progress": progress}), 200

@app.route('/api/crop_details', methods=['GET'])
def get_crop_details():
    crop = request.args.get('crop')
    if not crop or crop not in crop_details:
        return jsonify({"error": "Invalid crop"}), 400
    return jsonify(crop_details[crop]), 200

@app.route('/api/thingspeak_moisture', methods=['GET'])
def get_thingspeak_moisture():
    farmer_id = request.args.get('farmer_id')
    if not farmer_id:
        return jsonify({"error": "Farmer ID required"}), 400

    # Replace with your ThingSpeak channel ID and API key
    CHANNEL_ID = "YOUR_THINGSPEAK_CHANNEL_ID"
    API_KEY = "YOUR_THINGSPEAK_API_KEY"
    THINGSPEAK_URL = f"https://api.thingspeak.com/channels/{CHANNEL_ID}/feeds.json?api_key={API_KEY}&results=1"

    try:
        response = requests.get(THINGSPEAK_URL)
        response.raise_for_status()
        data = response.json()
        if data['feeds']:
            last_feed = data['feeds'][0]
            last_value = last_feed.get('field1', 'N/A')  # Assuming field1 is moisture
            last_updated = last_feed.get('created_at', 'N/A')
            return jsonify({"last_value": last_value, "last_updated": last_updated})
        return jsonify({"error": "No data available"}), 404
    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Failed to fetch ThingSpeak data: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
