from flask import Flask, request, jsonify
from flask_cors import CORS
import random
from datetime import datetime, timedelta

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
            "Growth Conditions": "Tomatoes thrive in well-drained, fertile soil with a pH of 6.0-6.8. They need full sun (6-8 hours daily) and temperatures between 20°C to 30°C.",
            "Care Tips": "Water consistently (1-2 inches per week), use stakes or cages for support, and apply mulch to retain moisture. Fertilize with a balanced 10-10-10 fertilizer.",
            "Harvest Time": "60-80 days after planting, when fruits are firm and fully colored.",
            "Pests": "Watch for aphids, whiteflies, and tomato hornworms. Use neem oil for organic control."
        }
    },
    "Rice": {
        "image_url": "https://images.unsplash.com/photo-1592918319975-86a7b78c5c3d?auto=format&fit=crop&w=500&q=80",
        "details": {
            "Growth Conditions": "Rice grows best in flooded fields with clayey soil, pH 5.5-7.0, and temperatures between 20°C to 37°C.",
            "Care Tips": "Maintain 2-5 cm of standing water during early growth, reduce water as plants mature. Use nitrogen-rich fertilizers like urea.",
            "Harvest Time": "90-150 days depending on the variety, when grains are golden and firm.",
            "Pests": "Monitor for stem borers and leaf folders. Use organic pesticides like neem extracts."
        }
    },
    "Wheat": {
        "image_url": "https://images.unsplash.com/photo-1591984472815-5b3b4b5f6c1e?auto=format&fit=crop&w=500&q=80",
        "details": {
            "Growth Conditions": "Wheat prefers well-drained loamy soil, pH 6.0-7.5, and cooler temperatures (15°C-25°C).",
            "Care Tips": "Sow in rows 20 cm apart, irrigate 4-5 times during the season, and apply phosphorus-based fertilizers at sowing.",
            "Harvest Time": "90-120 days, when grains are hard and straw turns golden.",
            "Pests": "Aphids and rust are common. Use resistant varieties and organic sprays."
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
    return jsonify({"stage": stage, "progress": random.randint(10, 100)}), 200

@app.route('/api/crop_details', methods=['GET'])
def get_crop_details():
    crop = request.args.get('crop')
    if not crop or crop not in crop_details:
        return jsonify({"error": "Invalid crop"}), 400
    return jsonify(crop_details[crop]), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
