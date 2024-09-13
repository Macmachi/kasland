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
DB_NAME = os.path.join(BASE_DIR, "database_name.db")

# Kaspa API configuration
KASPA_API_BASE_URL = "https://api.kaspa.example.org"

# Redistribution percentage configuration
COMMUNITY_FUNDING_PERCENTAGE = 0.XX  # Percentage for community funding
REDISTRIBUTION_PERCENTAGE = 0.XX  # Percentage for redistribution

# Time zone configuration
GAME_TIMEZONE = pytz.timezone('Europe/Berlin')

# Main Kaspa address for the game
KASPA_MAIN_ADDRESS = "kaspa:example_address_for_main_game_wallet"

# Game map configuration
MAP_SIZE = XX  # Size of the game map
PARCELS_PER_ROW = XX  # Number of parcels per row
TOTAL_PARCELS_DESIRED = XXXX  # Total number of desired parcels

# Check interval configuration
CHECK_INTERVAL = XX  # Check interval in seconds

# Minimum purchase amount configuration
MINIMUM_PURCHASE_AMOUNT = X  # Minimum purchase amount in KAS

# Building types configuration
BUILDING_TYPES = [
    {
        "name": "example_building",
        "min_amount": X,
        "max_amount": X,
        "fee_amount": X.X,
        "fee_frequency": XX,
        "building_category": "category",
        "energy_consumption": X,
        "zkaspa_production": X.X,
        "variants": [("A", 0.XX), ("B", 0.XX), ("C", 0.XX), ("D", 0.XX), ("E", 0.XX), ("F", 0.XXX), ("G", 0.XXX)],
        "max_count": None
    },
    # Add other building types following the same model
]

# Building bonus
WIND_TURBINE_BONUS = X.X  # Bonus for wind turbines

# Grace period configuration
GRACE_PERIOD_ENABLED = True  # or False
GRACE_PERIOD_DAYS = X  # Number of grace period days

# Logs configuration
LOG_FILE_NAME = os.path.join(BASE_DIR, 'logs', 'app.log')

# CORS configuration
ALLOWED_ORIGINS = ['https://example1.com', 'https://example2.com']

# Secret key configuration
SECRET_KEY = os.environ.get('SECRET_KEY') or 'default_development_key'

# Sessions configuration
SESSION_FILE_DIR = os.path.join(BASE_DIR, 'flask_session')
SESSION_TYPE = 'filesystem'
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_SECURE = True  # Set to False for local development without HTTPS

# Limiter Configuration
LIMITER_STORAGE_URI = "redis://localhost:6379/0" 
RATE_LIMIT_DAY = "XXXX per day"
RATE_LIMIT_HOUR = "XXX per hour"