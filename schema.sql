CREATE TABLE farmers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    email TEXT UNIQUE,
    password TEXT
);

CREATE TABLE farm_data (
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
);
