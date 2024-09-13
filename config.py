'''
KasLand Application
Copyright (c) 2024 Rymentz (rymentz.studio@gmail.com)

This work is licensed under the Creative Commons Attribution-NonCommercial 4.0 
International License. To view a copy of this license, visit:
http://creativecommons.org/licenses/by-nc/4.0/

You are free to:
- Share: copy and redistribute the material in any medium or format
- Adapt: remix, transform, and build upon the material

Under the following terms:
- Attribution: You must give appropriate credit, provide a link to the license,
  and indicate if changes were made.
- NonCommercial: You may not use the material for commercial purposes.

For any commercial use or licensing inquiries, please contact: rymentz.studio@gmail.com
'''

import os
import pytz

# Base path of the application
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# Database configuration
DB_NAME = os.path.join(BASE_DIR, "kasland.db")

# Kaspa API configuration
KASPA_API_BASE_URL = "https://api.kaspa.org"

# Redistribution percentage configuration
COMMUNITY_FUNDING_PERCENTAGE = 0.15
REDISTRIBUTION_PERCENTAGE = 0.15

# Time zone configuration
BERLIN_TZ = pytz.timezone('Europe/Berlin')

# Main Kaspa address for the game
KASPA_MAIN_ADDRESS = "kaspa:qpyps5d97q2cc5xghytl2wpxdljlk5ndglxt9f6c8hmrlev779rd544fmjhy0"

# Game map configuration
MAP_SIZE = 46
PARCELS_PER_ROW = 46
TOTAL_PARCELS_DESIRED = 1000

# Check interval configuration
CHECK_INTERVAL = 60

# Minimum purchase amount configuration
MINIMUM_PURCHASE_AMOUNT = 2

# ATTENTION ALWAYS UPDATE THE LEGENDS IN THE HTML FILE AFTER MODIFICATIONS HERE + DISCORD GUIDE!
# Applied bonuses are not visible here!
# ATTENTION 0.2 and 0.3 reserved for sale proposal and sale cancellation
BUILDING_TYPES = [
    {"name": "small_house", "min_amount": MINIMUM_PURCHASE_AMOUNT, "max_amount": 3, "fee_amount": 0.5, "fee_frequency": 90, "building_category": "residential", "energy_consumption": 5, "zkaspa_production": 0.1, "variants": [("A", 0.41), ("B", 0.30), ("C", 0.15), ("D", 0.08), ("E", 0.04), ("F", 0.015), ("G", 0.001)], "max_count": None},
    {"name": "wind_turbine_1", "min_amount": 5, "max_amount": 6, "fee_amount": 0.5, "fee_frequency": 90, "building_category": "energy", "energy_production": 50, "zkaspa_production": 0.2, "variants": [("A", 0.41), ("B", 0.30), ("C", 0.15), ("D", 0.08), ("E", 0.04), ("F", 0.015), ("G", 0.001)], "max_count": None},  
    # Comment out for BETA HERE AND IN HTML and IMAGES in static folder, attention add mini_farm2 and variants check figma file!
    # Reveal building by building!
    #{"name": "medium_house", "min_amount": 10, "max_amount": 11, "fee_amount": 0.5, "fee_frequency": 90, "building_category": "residential", "energy_consumption": 10, "zkaspa_production": 0.3, "variants": [("A", 0.40), ("B", 0.30), ("C", 0.15), ("D", 0.08), ("E", 0.05), ("F", 0.015), ("G", 0.001)], "max_count": None},
    #{"name": "large_house", "min_amount": 20, "max_amount": 21, "fee_amount": 0.5, "fee_frequency": 90, "building_category": "residential", "energy_consumption": 15, "zkaspa_production": 0.4, "variants": [("A", 0.39), ("B", 0.30), ("C", 0.15), ("D", 0.08), ("E", 0.06), ("F", 0.015), ("G", 0.001)], "max_count": None},
    #{"name": "manor", "min_amount": 30, "max_amount": 31, "fee_amount": 0.5, "fee_frequency": 90, "building_category": "residential", "energy_consumption": 20, "zkaspa_production": 0.8, "variants": [("A", 0.38), ("B", 0.30), ("C", 0.15), ("D", 0.08), ("E", 0.07), ("F", 0.015), ("G", 0.001)], "max_count": None},
    #{"name": "wind_turbine_2", "min_amount": 40, "max_amount": 41, "fee_amount": 0.5, "fee_frequency": 60, "building_category": "energy", "energy_production": 200, "zkaspa_production": 1, "variants": [("A", 0.37), ("B", 0.30), ("C", 0.15), ("D", 0.08), ("E", 0.08), ("F", 0.015), ("G", 0.001)], "max_count": None},  
    #{"name": "mining_farm_1", "min_amount": 50, "max_amount": 51, "fee_amount": 0.5, "fee_frequency": 30, "building_category": "mining", "energy_consumption": 100, "zkaspa_production": 1.5, "variants": [("A", 0.36), ("B", 0.30), ("C", 0.15), ("D", 0.08), ("E", 0.09), ("F", 0.015), ("G", 0.001)], "max_count": None},
    # Special & limited building 
    #{"name": "shai_house", "min_amount": 499, "max_amount": 500, "fee_amount": 0.5, "fee_frequency": 90, "building_category": "residential", "energy_consumption": 30, "zkaspa_production": 1.0, "variants": [("A", 0.30), ("B", 0.25), ("C", 0.20), ("D", 0.15), ("E", 0.08), ("F", 0.015), ("G", 0.001)], "max_count": 1},
]

# Building bonus
WIND_TURBINE_BONUS = 1.1

# Activation of the grace period for fee payments
GRACE_PERIOD_ENABLED = True
# Grace period duration in days for fee payment
# Remember to also modify in script.js: gracePeriodInSeconds
GRACE_PERIOD_DAYS = 7

# Logs configuration
LOG_FILE_NAME = os.path.join(BASE_DIR, 'logs', 'app.log')

# CORS configuration
ALLOWED_ORIGINS = ['https://kasland.org', 'https://www.kasland.org', 'http://localhost:8000', 'http://127.0.0.1:8000']

# Secret key configuration
SECRET_KEY = os.urandom(24)

# Sessions configuration
SESSION_FILE_DIR = os.path.join(BASE_DIR, 'flask_session')
SESSION_TYPE = 'filesystem'
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_SECURE = True  # If using HTTPS

# Limiter Configuration
LIMITER_STORAGE_URI = "memory://"
RATE_LIMIT_DAY = "1500 per day"
RATE_LIMIT_HOUR = "500 per hour"