'''
KasLand Application
Version: v0.9.2.0

Copyright (c) 2024 Rymentz (rymentz.studio@gmail.com)

Source Code License:
The source code of this application is licensed under the Creative Commons 
Attribution-NonCommercial 4.0 International License (CC BY-NC 4.0).

You are free to:
- Share: copy and redistribute the source code in any medium or format
- Adapt: remix, transform, and build upon the source code

Under the following terms:
- Attribution: You must give appropriate credit, provide a link to the license, 
  and indicate if changes were made.
- NonCommercial: You may not use the source code for commercial purposes.

This is a human-readable summary of (and not a substitute for) the license. 
For the full license text, please visit:
https://creativecommons.org/licenses/by-nc/4.0/legalcode

Game Assets:
All game assets (including but not limited to graphics, audio, and text content) 
are not covered by the CC BY-NC 4.0 license and are subject to separate copyright. 
These assets may not be used, reproduced, or distributed without explicit written 
permission from Rymentz.

The KasLand application as a whole, including its source code, software components, 
and assets, is protected by copyright laws and international treaty provisions.

Any use of this work outside the scope of these terms, including any commercial use, 
is prohibited without prior written permission.

For commercial use, licensing inquiries, or permission to use game assets, 
please contact: rymentz.studio@gmail.com 
'''

# [IMPORTS]

# Web framework to create the application
from flask import Flask, request, jsonify, render_template, abort, session, g, has_request_context
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_session import Session  
# Interface for SQLite database
import sqlite3
# Library to perform HTTP requests
import requests
from requests.exceptions import RequestException
# Date and duration management
from datetime import datetime, timedelta, timezone
# Time zone management
import pytz
# Background task scheduler
from apscheduler.schedulers.background import BackgroundScheduler
# Time-related functions
import time
# Random number generation
import random
# For saving logs and DB backup
import os
import shutil
# Also to check the validity of vendor addresses
import re
# For clean application shutdown
import signal
import sys
# Transaction order management
from operator import itemgetter
# ThreadPoolExecutor to manage scheduler tasks
from apscheduler.executors.pool import ThreadPoolExecutor
# Import configuration
from config import *

# Get the absolute path of the directory containing your application
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
# Create the 'logs' folder if it doesn't exist
log_directory = os.path.join(BASE_DIR, 'logs')
os.makedirs(log_directory, exist_ok=True)

app = Flask(__name__)

# CORS Configuration (APIs cannot be accessed from outside)
CORS(app, resources={r"/api/*": {"origins": ALLOWED_ORIGINS}})

'''
# Limiter Configuration (To prevent API abuse)
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=[RATE_LIMIT_DAY, RATE_LIMIT_HOUR],
    storage_uri=LIMITER_STORAGE_URI
)
'''
# Session secret key
app.config['SECRET_KEY'] = SECRET_KEY

# Session type configuration
app.config['SESSION_FILE_DIR'] = SESSION_FILE_DIR
app.config['SESSION_TYPE'] = SESSION_TYPE

# Ensure the session folder exists
os.makedirs(app.config['SESSION_FILE_DIR'], exist_ok=True)

# Existing configurations
app.config['SESSION_COOKIE_HTTPONLY'] = SESSION_COOKIE_HTTPONLY
app.config['SESSION_COOKIE_SAMESITE'] = SESSION_COOKIE_SAMESITE
app.config['SESSION_COOKIE_SECURE'] = SESSION_COOKIE_SECURE

Session(app)

# Avoid having logs every minute for the sale of players' plots
last_log_time = None

@app.before_request
def check_origin():
    if request.method != 'OPTIONS':
        origin = request.headers.get('Origin')
        if origin:
            if origin not in ALLOWED_ORIGINS:
                abort(403)
        else:
            # If no origin, it's probably a local nginx request
            if request.remote_addr not in ['127.0.0.1', 'localhost']:
                abort(403)

'''
Saves timestamped messages in a log file, useful for tracking and debugging the application.
'''
def log_message(message: str):
    with open(LOG_FILE_NAME, "a") as log_file:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_file.write(f"{timestamp} - {message}\n")
        log_file.flush()

"""
Performs log file rotation.
- Checks if the current log file is more than 30 days old.
    If so, it is archived with a timestamp and a new empty log file is created.
- Archived files are stored in an 'archives' subdirectory.
- If the current log file doesn't exist, a new one is created.
"""
def rotate_logs():
    try:
        current_time = datetime.now()
        current_log_file = os.path.join(log_directory, 'app.log')
        
        # Check if the current log file exists and is older than 30 days
        if os.path.exists(current_log_file):
            file_modification_time = datetime.fromtimestamp(os.path.getmtime(current_log_file))
            if (current_time - file_modification_time) > timedelta(days=30):
                # Create a filename for the archive
                archive_filename = f'app_{file_modification_time.strftime("%Y%m%d")}.log'
                archive_path = os.path.join(log_directory, 'archives', archive_filename)
                
                # Create the archive directory if it doesn't exist
                os.makedirs(os.path.dirname(archive_path), exist_ok=True)
                
                # Copy the current log file to the archives
                shutil.copy2(current_log_file, archive_path)
                
                # Create a new empty log file
                open(current_log_file, 'w').close()
                
                log_message(f"Log rotation completed. Old log archived: {archive_filename}")
            else:
                log_message("Current log file is less than 30 days old. No rotation needed.")
        else:
            log_message("No log file found. Creating a new file.")
            open(current_log_file, 'w').close()
        
    except Exception as e:
        log_message(f"Error during log rotation: {e}")

"""
Performs a database backup.
- Creates a backup folder if it doesn't exist.
- Generates a dated backup file and a 'latest' copy.
- Deletes backups older than 14 days.
- Handles exceptions related to files, permissions, and other errors.
- Records actions and errors in the logs.
"""
def backup_database():
    try:
        # Create a folder for backups if it doesn't exist
        backup_dir = os.path.join(BASE_DIR, 'backups')
        os.makedirs(backup_dir, exist_ok=True)

        # Backup file name with the current date
        current_date = datetime.now().strftime("%Y%m%d")
        backup_file = os.path.join(backup_dir, f'kasland_backup_{current_date}.db')

        # Copy the current database
        shutil.copy2(DB_NAME, backup_file)

        # Keep a copy with a fixed name for easy access to the latest backup
        latest_backup = os.path.join(backup_dir, 'kasland_backup_latest.db')
        shutil.copy2(backup_file, latest_backup)

        log_message(f"Database backup completed: {backup_file}")

        # Delete old backups (more than 14 days old)
        for old_file in os.listdir(backup_dir):
            if old_file.startswith('kasland_backup_') and old_file.endswith('.db') and old_file != 'kasland_backup_latest.db':
                file_path = os.path.join(backup_dir, old_file)
                match = re.match(r'kasland_backup_(\d{8})\.db', old_file)
                if match:
                    try:
                        file_date = datetime.strptime(match.group(1), "%Y%m%d")
                        if datetime.now() - file_date > timedelta(days=14):
                            os.remove(file_path)
                            log_message(f"Old backup deleted: {old_file}")
                    except ValueError as e:
                        log_message(f"Error parsing date for file {old_file}: {e}")
                else:
                    log_message(f"Backup file ignored (invalid name format): {old_file}")

    except FileNotFoundError:
        log_message("Error: Source database file does not exist. No backup performed.")
    except PermissionError:
        log_message("Error: Insufficient permissions to perform the backup.")
    except Exception as e:
        log_message(f"Unexpected error during database backup: {e}")

"""
Handles the clean shutdown of the program.
- Logs a message to signal the shutdown.
- Stops the task scheduler.
- Waits briefly to allow ongoing operations to finalize.
- Terminates the program with exit code 0 (success).

This function is configured to respond to SIGINT (Ctrl+C) and SIGTERM signals.
"""
def signal_handler(sig, frame):
    log_message("Shutting down the server...")
    
    # Stop the scheduler
    if scheduler.running:
        scheduler.shutdown(wait=False)
    
    # Properly terminate database connections
    # (if you have a connection pool, for example)
    #close_db_connections()
    time.sleep(1)  # Wait 1 second before exiting
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

"""
Establishes and returns a connection to the SQLite database.
Configures the connection to return Row type objects.
Used in all functions requiring database access.
"""
def get_db_connection():
    try:
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        log_message(f"Error connecting to the database: {e}")
        return None

"""
Determines the building type and variant based on the sent amount.

Operation:
1. Retrieves building types from the database if not provided.
2. Selects the highest possible building type less than or equal to the given amount.
3. Respects quantity limits for each building type.
4. In case of exact overlap between two types, chooses the lower type.
5. Checks if the maximum number of buildings of each type has been reached.
6. If the highest type has reached its limit, moves to the next available lower type.
7. Chooses a variant:
   - Keeps the current variant if provided and valid.
   - Otherwise, randomly selects a variant according to defined probabilities.
8. Handles database errors and unexpected exceptions.

Parameters:
- amount (float): The amount for which to determine the building type.
- current_variant (str, optional): The current building variant, if applicable.
- building_types (list, optional): List of available building types. 
  If not provided, it will be retrieved from the database.

Returns:
- tuple: (building_type, variant) or (None, None) if no appropriate type is found.

Note:
- The function handles different formats for building_types (sqlite3.Row, dict, or tuple),
  allowing flexibility in the source of building type data.
- Uses a database connection to retrieve necessary information.
- Logs detailed messages for tracking the determination process.
"""
def determine_building_type(amount, current_variant=None, building_types=None):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            # If building_types is not provided, retrieve it from the database
            if building_types is None:
                cursor.execute('''
                    SELECT bt.*, 
                           GROUP_CONCAT(bv.variant || ':' || bv.probability, ';') as variants
                    FROM building_types bt
                    LEFT JOIN building_variants bv ON bt.name = bv.building_type
                    GROUP BY bt.name
                    ORDER BY bt.min_amount DESC
                ''')
                building_types = [dict(row) for row in cursor.fetchall()]
                for bt in building_types:
                    if bt['variants']:
                        bt['variants'] = [tuple(v.split(':')) for v in bt['variants'].split(';')]
                        bt['variants'] = [(v[0], float(v[1])) for v in bt['variants']]
                    else:
                        bt['variants'] = []
            
            log_message(f"Attempting to determine building type for amount {amount}")
            log_message(f"Available building types: {[b['name'] if isinstance(b, dict) else b[0] for b in building_types]}")

            suitable_type = None
            for building in building_types:
                # Handling different data types for building_types
                if isinstance(building, sqlite3.Row):
                    # If building is a Row object
                    name = building['name']
                    min_amount = building['min_amount']
                    max_count = building['max_count'] if 'max_count' in building.keys() else None
                    variants = None
                elif isinstance(building, dict):
                    # If building is a dictionary
                    name = building['name']
                    min_amount = building['min_amount']
                    max_count = building.get('max_count')
                    variants = building.get('variants', [])
                else:
                    # If building is a tuple (default case)
                    name, min_amount, _, max_count = building
                    variants = None
                
                if amount >= min_amount:
                    # Check if the maximum number of this building type has been reached
                    if max_count is not None:
                        cursor.execute('''
                            SELECT COUNT(*) 
                            FROM parcels 
                            WHERE building_type = ?
                        ''', (name,))
                        count = cursor.fetchone()[0]
                        if count >= max_count:
                            log_message(f"Maximum number reached for {name}")
                            continue  # Move to the next building type if max is reached
                    
                    suitable_type = name
                    suitable_variants = variants
                    break  # We found the appropriate building type, exit the loop

            if suitable_type:
                if suitable_variants is None:
                    # Retrieve variants and their probabilities for this building type
                    cursor.execute('''
                        SELECT variant, probability
                        FROM building_variants
                        WHERE building_type = ?
                    ''', (suitable_type,))
                    suitable_variants = cursor.fetchall()
                
                if suitable_variants:
                    # If a current variant is provided and valid, keep it
                    if current_variant and any(v[0] == current_variant for v in suitable_variants):
                        variant = current_variant
                    else:
                        # Select a new variant based on probabilities
                        variant_names = [v[0] for v in suitable_variants]
                        probabilities = [v[1] for v in suitable_variants]
                        variant = random.choices(variant_names, weights=probabilities, k=1)[0]
                else:
                    log_message(f"No variant found for {suitable_type}, using default variant 'A'")
                    variant = 'A'  # Default variant if none is found
                
                log_message(f"Selected building type: {suitable_type}, variant: {variant}")
                return suitable_type, variant
            else:
                log_message(f"No suitable building type found for amount {amount}")
                return None, None

        except Exception as e:
            log_message(f"Error executing main query: {e}")
            return None, None

    except Exception as e:
        log_message(f"Error connecting to database: {e}")
        return None, None

    finally:
        if conn:
            conn.close()

    return None, None

'''
Function to update fee dates!
Very important if we change the fee frequency for a building type that it's reflected everywhere!
'''
def update_fee_dates_for_building_type(conn, cursor, building_type, new_fee_frequency):
    current_time = time.time()
    cursor.execute("""
        UPDATE parcels
        SET fee_frequency = ?,
            next_fee_date = ? + (? * 24 * 60 * 60)
        WHERE building_type = ?
    """, (new_fee_frequency, current_time, new_fee_frequency, building_type))
    log_message(f"Updated fee dates for building type {building_type}")

'''
init_db():
Initializes and updates the game's database.

Process:
1. Creates necessary tables if they don't exist.
2. Updates existing building types and adds new types.
3. Updates building variants.
4. Updates characteristics of existing plots for each building type.
5. Checks and updates all building types for existing plots in a single pass:
   - Handles both changes to existing types and newly added types.
   - Updates all relevant characteristics (fee_amount, fee_frequency, energy_consumption, etc.).
6. Adds new plots if necessary to reach the desired total number.
7. Recalculates the map size.
8. Updates game statistics and parameters.
9. Handles updating variants for existing plots, ensuring they are valid.
10. Saves modifications and logs important information at each step.

This function ensures the database is up to date with the latest building configurations,
including newly added types and modifications to existing characteristics,
while preserving data integrity and optimizing the update process.

'''
def init_db():
    global MAP_SIZE
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        log_message("Initializing database...")

        # Block for table creation
        try:   
            # Create tables if they don't already exist
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS parcels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    owner_address TEXT,
                    building_type TEXT,
                    building_variant TEXT,
                    purchase_amount REAL,
                    purchase_date REAL,
                    last_fee_payment REAL,
                    last_fee_check REAL,
                    last_fee_amount REAL,
                    fee_frequency INTEGER,
                    next_fee_date REAL,
                    x INTEGER,
                    y INTEGER,
                    energy_production INTEGER DEFAULT 0,
                    energy_consumption INTEGER DEFAULT 0,
                    zkaspa_production REAL DEFAULT 0,
                    zkaspa_balance REAL DEFAULT 0,
                    is_special BOOLEAN DEFAULT 0,
                    is_for_sale BOOLEAN DEFAULT 0,
                    sale_price REAL,
                    type TEXT DEFAULT 'grass',
                    rarity TEXT
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS processed_transactions (
                    transaction_id TEXT PRIMARY KEY,
                    processed_at REAL
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS wallets (
                    address TEXT PRIMARY KEY,
                    total_amount REAL,
                    transaction_count INTEGER,
                    last_transaction_id TEXT,
                    last_transaction_timestamp REAL
                )
            ''')
            
            # Create a new table to store game parameters
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS game_parameters (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            ''')

            # Create the table for building types
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS building_types (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE,
                    min_amount REAL,
                    max_amount REAL,
                    fee_amount REAL,
                    fee_frequency INTEGER,
                    building_category TEXT,
                    energy_production INTEGER,
                    energy_consumption INTEGER,
                    zkaspa_production REAL,
                    max_count INTEGER
                )
            ''')

            # Create the table for building variants
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS building_variants (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    building_type TEXT,
                    variant TEXT,
                    probability REAL,
                    UNIQUE(building_type, variant)
                )
            ''')

            # Create the table for fee payments
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS fee_payments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    parcel_id INTEGER,
                    payment_date REAL,
                    amount REAL,
                    building_type TEXT,
                    FOREIGN KEY (parcel_id) REFERENCES parcels(id)
                )
            ''')

            # Create the table for random events
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT,
                    start_time REAL,
                    end_time REAL,
                    description TEXT,
                    energy_multiplier REAL,
                    zkaspa_multiplier REAL
                )
            ''')

            # Create the table for daily statistics
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS daily_stats (
                    date DATE PRIMARY KEY,
                    total_energy_production INTEGER,
                    total_energy_consumption INTEGER,
                    total_zkaspa REAL,
                    predicted_zkaspa_production REAL,
                    actual_zkaspa_production REAL
                )
            ''')

            # Create the table for wallets to monitor for parcel sales
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS wallets_to_monitor (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    address TEXT NOT NULL,
                    expected_amount REAL NOT NULL,
                    parcel_id INTEGER NOT NULL,
                    created_at REAL NOT NULL,
                    status TEXT DEFAULT 'pending',
                    FOREIGN KEY (parcel_id) REFERENCES parcels(id)
                )
            ''')

        except sqlite3.Error as e:
            log_message(f"Error creating tables: {e}")
            raise  

        # Get the current list of building types (allows to know which buildings have been added to the building type list from existing ones)
        cursor.execute("SELECT name FROM building_types")
        existing_building_types = set(row['name'] for row in cursor.fetchall())
       
        # Initialize the set for new building types
        new_building_types = set()

        log_message("Updating building types and existing parcels...")

        for building in BUILDING_TYPES:
            cursor.execute('''
                SELECT fee_frequency
                FROM building_types
                WHERE name = ?
            ''', (building['name'],))
            old_frequency = cursor.fetchone()
            
            cursor.execute('''
                INSERT OR REPLACE INTO building_types 
                (name, min_amount, max_amount, fee_amount, fee_frequency, building_category,
                energy_production, energy_consumption, zkaspa_production, max_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                building['name'],
                building['min_amount'],
                building['max_amount'],
                building['fee_amount'],
                building['fee_frequency'],
                building['building_category'],
                building.get('energy_production', 0),
                building.get('energy_consumption', 0),
                building['zkaspa_production'],
                building.get('max_count', None)
            ))
            new_building_types.add(building['name'])

            if old_frequency and old_frequency[0] != building['fee_frequency']:
                update_fee_dates_for_building_type(conn, cursor, building['name'], building['fee_frequency'])

            log_message(f"Building type '{building['name']}' updated in the database.")

            # Update existing parcels with new values
            cursor.execute('''
                UPDATE parcels
                SET last_fee_amount = ?,
                    fee_frequency = ?,
                    energy_production = ?,
                    energy_consumption = ?,
                    zkaspa_production = ?
                WHERE building_type = ?
            ''', (
                building.get('fee_amount', 0),
                building.get('fee_frequency', 0),
                building.get('energy_production', 0),
                building.get('energy_consumption', 0),
                building.get('zkaspa_production', 0),
                building['name']
            ))
                                    
            updated_rows = cursor.rowcount
            log_message(f"{updated_rows} parcels updated for type '{building['name']}'.")

            # Modify this part to insert variants with their probabilities
            cursor.executemany('''
                INSERT OR REPLACE INTO building_variants (building_type, variant, probability)
                VALUES (?, ?, ?)
            ''', [(building['name'], variant, probability) for variant, probability in building['variants']])
            log_message(f"Variants updated for type '{building['name']}'.")

        # Refresh the list of building types after updates
        cursor.execute('''
            SELECT bt.*, 
                GROUP_CONCAT(bv.variant || ':' || bv.probability, ';') as variants
            FROM building_types bt
            LEFT JOIN building_variants bv ON bt.name = bv.building_type
            GROUP BY bt.name
            ORDER BY bt.min_amount DESC
        ''')
        building_types = [dict(row) for row in cursor.fetchall()]

        # Convertir la chaîne de variantes en liste de tuples
        for bt in building_types:
            if bt['variants']:
                bt['variants'] = [tuple(v.split(':')) for v in bt['variants'].split(';')]
                bt['variants'] = [(v[0], float(v[1])) for v in bt['variants']]
            else:
                bt['variants'] = []

        log_message(f"Updated building types: {[b['name'] for b in building_types]}")

        # Check updated parcels
        cursor.execute('''
            SELECT building_type, COUNT(*) as count
            FROM parcels
            WHERE owner_address IS NOT NULL
            GROUP BY building_type
        ''')
        building_counts = cursor.fetchall()
        for building_type, count in building_counts:
            log_message(f"{building_type}: {count} parcels")

        # Check for newly added building types
        added_building_types = new_building_types - existing_building_types

        # Single check for all parcels
        log_message("\nVerification and update of building types for all parcels:")
        cursor.execute('''
            SELECT id, building_type, building_variant, purchase_amount, owner_address
            FROM parcels
            WHERE owner_address IS NOT NULL
        ''')
        all_parcels = cursor.fetchall()

        for parcel in all_parcels:
            parcel_id, current_building_type, current_building_variant, purchase_amount, owner_address = parcel
            new_building_type, new_variant = determine_building_type(purchase_amount, current_building_variant, building_types)
            
            # Check if the building type has changed, if it's a new type, or if an update is necessary
            if new_building_type != current_building_type or new_building_type in added_building_types:
                cursor.execute('''
                    UPDATE parcels
                    SET building_type = ?, building_variant = ?
                    WHERE id = ?
                ''', (new_building_type, new_variant, parcel_id))
                
                building_info = next((b for b in BUILDING_TYPES if b['name'] == new_building_type), None)
                if building_info:
                    cursor.execute('''
                        UPDATE parcels
                        SET last_fee_amount = ?, fee_frequency = ?, 
                            energy_consumption = ?, energy_production = ?, zkaspa_production = ?
                        WHERE id = ?
                    ''', (building_info['fee_amount'], building_info['fee_frequency'],
                        building_info.get('energy_consumption', 0), building_info.get('energy_production', 0),
                        building_info.get('zkaspa_production', 0), parcel_id))
                log_message(f"Parcel {parcel_id} updated: {current_building_type} -> {new_building_type}")
            elif not new_building_type:
                log_message(f"No appropriate new building type found for parcel {parcel_id}. Current type retained: {current_building_type}")

        for new_type in added_building_types:
            log_message(f"Checking newly added building type(s): {new_type}")   

        # Check the number of existing parcels
        log_message("Checking existing parcels...")
        cursor.execute("SELECT COUNT(*) FROM parcels")
        existing_parcels = cursor.fetchone()[0]
        log_message(f"Number of existing parcels: {existing_parcels}")

        if existing_parcels < TOTAL_PARCELS_DESIRED:
            log_message(f"Adding {TOTAL_PARCELS_DESIRED - existing_parcels} new parcels...")

            # Find the maximum existing index
            cursor.execute("SELECT MAX(x * ? + y) as max_index FROM parcels", (PARCELS_PER_ROW,))
            max_index = cursor.fetchone()[0]
            if max_index is None:
                max_index = -1

            # Add new parcels
            parcels_to_add = []
            while existing_parcels < TOTAL_PARCELS_DESIRED:
                max_index += 1
                x = max_index // PARCELS_PER_ROW
                y = max_index % PARCELS_PER_ROW

                parcels_to_add.append((x, y))
                existing_parcels += 1

            # Insert all new parcels in a single query
            cursor.executemany('''
                INSERT INTO parcels (x, y, owner_address, building_type, purchase_amount, purchase_date,
                                    last_fee_payment, last_fee_check, last_fee_amount, fee_frequency,
                                    next_fee_date, energy_production, energy_consumption, zkaspa_production,
                                    zkaspa_balance)
                VALUES (?, ?, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 0, 0, 0, 0)
            ''', parcels_to_add)

            log_message("New parcels added.")

        # Calculate the new map size
        MAP_SIZE = max((TOTAL_PARCELS_DESIRED - 1) // PARCELS_PER_ROW + 1, PARCELS_PER_ROW)

        log_message(f"Final number of parcels: {existing_parcels}")
        log_message(f"Final map size: {MAP_SIZE}x{PARCELS_PER_ROW}")

        cursor.execute("SELECT MIN(x), MAX(x), MIN(y), MAX(y) FROM parcels")
        min_max = cursor.fetchone()
        log_message(f"Coordinate range: x({min_max[0]}-{min_max[1]}), y({min_max[2]}-{min_max[3]})")

        # Update the map size in the database
        cursor.execute("INSERT OR REPLACE INTO game_parameters (key, value) VALUES (?, ?)", ('map_size', str(MAP_SIZE)))

        log_message("\nChecking updated parcels:")
        for building in BUILDING_TYPES:
            cursor.execute('''
                SELECT COUNT(*) as count, building_type, fee_frequency, energy_consumption, energy_production, zkaspa_production
                FROM parcels
                WHERE building_type = ?
                GROUP BY building_type, fee_frequency, energy_consumption, energy_production, zkaspa_production
            ''', (building['name'],))
            result = cursor.fetchone()
            if result:
                log_message(f"{building['name']}: {result['count']} parcels, "
                    f"fee_frequency={result['fee_frequency']}, "
                    f"energy_consumption={result['energy_consumption']}, "
                    f"energy_production={result['energy_production']}, "
                    f"zkaspa_production={result['zkaspa_production']}")
            else:
                log_message(f"{building['name']}: No parcels found")

        log_message(f"\nFinal number of parcels: {existing_parcels}")
        log_message(f"Final map size: {MAP_SIZE}x{PARCELS_PER_ROW}")

        cursor.execute("SELECT MIN(x), MAX(x), MIN(y), MAX(y) FROM parcels")
        min_max = cursor.fetchone()
        log_message(f"Coordinate range: x({min_max[0]}-{min_max[1]}), y({min_max[2]}-{min_max[3]})")

        # Handle updating variants for existing parcels
        log_message("\nUpdating variants for existing parcels:")
        for building in BUILDING_TYPES:
            cursor.execute('''
                SELECT id, building_variant
                FROM parcels
                WHERE building_type = ? AND owner_address IS NOT NULL
            ''', (building['name'],))
            
            parcels_to_update = cursor.fetchall()
            
            for parcel in parcels_to_update:
                current_variant = parcel['building_variant']
                if current_variant not in [v[0] for v in building['variants']]:
                    # Choose a new random variant if the old one no longer exists
                    new_variant = random.choices([v[0] for v in building['variants']], 
                                                weights=[v[1] for v in building['variants']])[0]
                    cursor.execute('''
                        UPDATE parcels
                        SET building_variant = ?
                        WHERE id = ?
                    ''', (new_variant, parcel['id']))
                    log_message(f"Parcel {parcel['id']} updated: old variant {current_variant} -> new variant {new_variant}")

        conn.commit()
        log_message("Database initialization completed successfully.")


    except sqlite3.Error as e:
        log_message(f"General database error: {e}")
        conn.rollback()
        raise

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

# Call init_db() at application startup
init_db()
      
'''
check_new_transactions():
Checks and processes new transactions for the main Kaspa address.

- Retrieves and sorts recent transactions.
- Processes each new transaction not yet recorded.
- Handles errors in data access and processing.
- Logs records for processed transactions and errors.
'''
def check_new_transactions():
    with app.app_context():
        try:
            transactions = get_recent_transactions(KASPA_MAIN_ADDRESS)
            
            # Sort transactions by timestamp
            sorted_transactions = sorted(transactions, key=itemgetter('block_time'))
            
            for tx in sorted_transactions:
                try:
                    tx_id = tx['transaction_id']
                    if not transaction_already_processed(tx_id):
                        for output in tx['outputs']:
                            if output['script_public_key_address'] == KASPA_MAIN_ADDRESS:
                                try:
                                    amount = output['amount'] / 100000000  # Conversion to KAS
                                    from_address = tx['inputs'][0].get('previous_outpoint_address', 'Unknown')
                                    
                                    # Process the transaction for fees and upgrades/allocations
                                    process_new_transaction(from_address, amount, tx_id, tx['block_time'])
                                    log_message(f"New transaction processed for {from_address}: {amount} KAS")
                                except KeyError as e:
                                    log_message(f"Error accessing transaction data: {e}")
                                except Exception as e:
                                    log_message(f"Unexpected error while processing transaction: {e}")
                except KeyError as e:
                    log_message(f"Error accessing transaction data: {e}")
                except Exception as e:
                    log_message(f"Unexpected error while processing transaction: {e}")
        except Exception as e:
            log_message(f"Error retrieving recent transactions: {e}")
            
"""
get_total_amount_sent(address):
Retrieves the total amount sent by a specific address.

Parameters:
- address (str): The wallet address to check.

Returns:
- float: The total amount sent, or 0 in case of error.

Used to determine a player's eligibility for certain game actions.
"""
def get_total_amount_sent(address):
    conn = None
    total_amount = 0
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT SUM(total_amount) FROM wallets WHERE address = ?", (address,))
            result = cursor.fetchone()
            if result and result[0] is not None:
                total_amount = result[0]
        except sqlite3.Error as e:
            log_message(f"SQLite error while retrieving total amount for address {address}: {e}")
    except Exception as e:
        log_message(f"Unexpected error while retrieving total amount for address {address}: {e}")
    finally:
        if conn:
            try:
                conn.close()
            except Exception as e:
                log_message(f"Error closing connection for address {address}: {e}")
    return total_amount

"""
get_unassigned_parcel():
Randomly retrieves an unassigned plot from the database.

Returns:
- tuple: (id, x, y) of the plot if available, None otherwise.

Used when assigning a new plot to a player.
"""
def get_unassigned_parcel():
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT id, x, y 
                FROM parcels 
                WHERE owner_address IS NULL 
                  AND (purchase_amount IS NULL OR purchase_amount = 0)
            """)
            unassigned_parcels = cursor.fetchall()
            
            if unassigned_parcels:
                return random.choice(unassigned_parcels)
            else:
                return None
        except sqlite3.Error as e:
            log_message(f"SQLite error while retrieving unassigned parcels: {e}")
            return None
    except Exception as e:
        log_message(f"Unexpected error while retrieving unassigned parcels: {e}")
        return None
    finally:
        if conn:
            try:
                conn.close()
            except Exception as e:
                log_message(f"Error closing connection: {e}")

"""
process_new_transaction(from_address, amount, tx_id, timestamp):
Processes a new transaction for a given address.

Parameters:
- from_address (str): Origin address of the transaction.
- amount (float): Transaction amount in KAS.
- tx_id (str): Unique transaction ID.
- timestamp (float): Transaction timestamp.

Returns:
- dict: Processing result with status and message.

Operation:
1. Checks if the transaction has already been processed.
2. Updates or inserts wallet information.
3. Checks the total amount sent by the address.
4. Determines the action to take based on the amount:
   - Plot listing for sale (about 0.2 KAS)
   - Sale cancellation (about 0.3 KAS)
   - Normal processing (other amounts)
5. For normal processing:
   - If the address already has a plot:
     * Checks if the plot is for sale and updates the price if necessary
     * Otherwise, processes fee payment and attempts an upgrade
   - If the address doesn't have a plot and the total amount is sufficient:
     * Assigns a new plot
   - Otherwise, returns an error message for insufficient amount
6. Marks the transaction as processed.

Handles various actions such as fee payment, building upgrade,
plot listing for sale, sale cancellation, and new plot assignment.
Updates the database accordingly and modifies the game state based on the type
and amount of the transaction.

Note:
- Uses a database connection for all operations.
- Handles database errors and unexpected exceptions.
- Logs detailed messages for transaction processing tracking.
"""
def process_new_transaction(from_address, amount, tx_id, timestamp):
    conn = None
    result = {"success": False, "message": "Unexpected error while processing the transaction."}
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        if transaction_already_processed(tx_id):
            return {"success": False, "message": "Transaction already processed."}

        try:
            # Update or insert wallet information
            update_wallet_info(from_address, amount, tx_id, timestamp)
            
            # Check the total amount sent by this address
            total_amount = get_total_amount_sent(from_address)
            
            current_time = datetime.now().timestamp()

            # Check if the address already has a parcel
            cursor.execute("SELECT * FROM parcels WHERE owner_address = ?", (from_address,))
            existing_parcel = cursor.fetchone()

            # Tolerate a margin of error for the sale action
            if abs(amount - 0.2) < 0.01:
                if existing_parcel:
                    # Process as a sale listing request or price update
                    if process_sale_listing(conn, cursor, from_address, tx_id):
                        result = {"success": True, "message": "Parcel successfully listed for sale or price updated."}
                    else:
                        result = {"success": False, "message": "Failed to list parcel for sale or update price."}
                else:
                    result = {"success": False, "message": "Unable to list for sale: you don't have a parcel."}
            # Tolerate a margin of error for the sale cancellation action
            elif abs(amount - 0.3) < 0.01:
                if existing_parcel:
                    # Process as a sale cancellation request
                    if process_sale_cancellation(conn, cursor, from_address, tx_id):
                        result = {"success": True, "message": "Sale cancellation successful."}
                    else:
                        result = {"success": False, "message": "Failed to cancel the sale."}
                else:
                    result = {"success": False, "message": "Unable to cancel sale: you don't have a parcel."}

            else:
                # New code: Check if the amount corresponds to a sale listing with multiplier
                multiplier = None
                tolerance = 0.01  # Adjust the tolerance as needed
                for key_amount in PRICE_MULTIPLIERS.keys():
                    if abs(amount - key_amount) < tolerance:
                        multiplier = PRICE_MULTIPLIERS[key_amount]
                        break

                if existing_parcel and multiplier:
                    # Process as a sale listing with multiplier
                    if process_sale_listing(conn, cursor, from_address, tx_id, multiplier=multiplier):
                        result = {"success": True, "message": f"Parcel listed for sale with price multiplier {multiplier}."}
                    else:
                        result = {"success": False, "message": "Failed to list parcel for sale with multiplier."}
                else:
                    # If it's not a special action, process as a normal transaction
                    if existing_parcel:
                        # Check if the parcel is already for sale
                        if existing_parcel['is_for_sale']:
                            # Update the sale price
                            if process_sale_listing(conn, cursor, from_address, tx_id):
                                result = {"success": True, "message": f"Sale price successfully updated. New amount: {total_amount} KAS"}
                            else:
                                result = {"success": False, "message": "Failed to update sale price."}
                        else:
                            result = process_existing_parcel(conn, cursor, from_address, amount, existing_parcel, current_time, tx_id)
                    elif total_amount >= MINIMUM_PURCHASE_AMOUNT:
                        result = process_new_parcel(conn, cursor, from_address, total_amount, current_time)
                    else:
                        result = {"success": False, "message": f"Insufficient amount. Minimum required amount: {MINIMUM_PURCHASE_AMOUNT} KAS."}

            # Mark the transaction as processed
            cursor.execute("INSERT INTO processed_transactions (transaction_id, processed_at) VALUES (?, ?)", (tx_id, time.time()))
            conn.commit()
            log_message(f"New transaction processed: {amount} KAS received from {from_address}. Result: {result['message']}")

        except sqlite3.Error as e:
            conn.rollback()
            log_message(f"SQL error while processing the transaction: {e}")
            result = {"success": False, "message": "Error while processing the transaction."}
        except Exception as e:
            conn.rollback()
            log_message(f"Unexpected error while processing the transaction: {e}")

    except sqlite3.Error as e:
        log_message(f"SQL error while connecting to the database: {e}")
        result = {"success": False, "message": "Error connecting to the database."}
    except Exception as e:
        log_message(f"Unexpected error while connecting to the database: {e}")
    finally:
        if conn:
            try:
                conn.close()
            except Exception as e:
                log_message(f"Error while closing the connection: {e}")
    
    return result

"""
Handles a transaction for an existing plot.

Parameters:
- conn: Database connection.
- cursor: Database cursor.
- from_address (str): Owner's address.
- amount (float): Transaction amount.
- existing_parcel (dict): Existing plot data.
- current_time (float): Current timestamp.
- tx_id (str): Transaction ID.

Returns:
- dict: Processing result with details on actions taken.

Processes fee payment and attempts a building upgrade, using the total amount for the upgrade regardless of fee payment.
"""
def process_existing_parcel(conn, cursor, from_address, amount, existing_parcel, current_time, tx_id):
    try:
        fee_paid = False
        upgrade_performed = False
        fee_amount = existing_parcel['fee_amount'] if 'fee_amount' in existing_parcel.keys() else 0

        # Check if fees are due
        if existing_parcel['next_fee_date'] <= current_time:
            if amount >= fee_amount:
                # Pay the fees without deducting from the upgrade amount
                new_next_fee_date = current_time + (existing_parcel['fee_frequency'] * 24 * 60 * 60)
                try:
                    cursor.execute("""
                        UPDATE parcels
                        SET last_fee_payment = ?, last_fee_check = ?, next_fee_date = ?
                        WHERE owner_address = ?
                    """, (current_time, current_time, new_next_fee_date, from_address))

                    # Record the fee payment
                    cursor.execute("""
                        INSERT INTO fee_payments (parcel_id, payment_date, amount, building_type, transaction_id)
                        VALUES (?, ?, ?, ?, ?)
                    """, (existing_parcel['id'], current_time, fee_amount, existing_parcel['building_type'], tx_id))

                    fee_paid = True
                    log_message(f"Fees of {fee_amount} KAS paid for {from_address}")
                except sqlite3.Error as e:
                    conn.rollback()
                    log_message(f"Error updating fees for {from_address}: {e}")
                    return {"success": False, "message": "Error while paying fees."}
            else:
                log_message(f"Insufficient payment to cover fees for {from_address}")
                return {"success": False, "message": "Insufficient payment to cover fees."}

        # Attempt upgrade with the total amount, regardless of fee payment
        upgrade_result = upgrade_building(conn, from_address, amount, is_buy_parcel=False, manage_transaction=True)
        upgrade_performed = upgrade_result['success'] if 'success' in upgrade_result else False

        # Prepare the result message
        result_message = []
        if fee_paid:
            result_message.append(f"Fees of {fee_amount} KAS paid.")
        if upgrade_performed:
            result_message.append(upgrade_result['message'] if 'message' in upgrade_result else "Upgrade performed.")
        else:
            result_message.append("No upgrade performed.")

        final_result = {
            "success": fee_paid or upgrade_performed,
            "message": " ".join(result_message),
            "fee_paid": fee_paid,
            "upgrade_performed": upgrade_performed
        }

        log_message(f"Processing for {from_address}: {final_result['message']}")
        return final_result

    except Exception as e:
        conn.rollback()
        log_message(f"Unexpected error while processing existing parcel for {from_address}: {e}")
        return {"success": False, "message": "Unexpected error while processing existing parcel."}
    
"""
process_new_parcel(conn, cursor, from_address, total_amount, current_time):
Assigns a new plot to a new user.

Parameters:
- conn: Database connection
- cursor: Database cursor
- from_address (str): Buyer's address
- total_amount (float): Total amount sent
- current_time (float): Current timestamp

Returns:
- dict: Assignment result with plot details or error message
"""
def process_new_parcel(conn, cursor, from_address, total_amount, current_time):
    try:
        unassigned_parcel = get_unassigned_parcel()
        if not unassigned_parcel:
            return {"success": False, "message": "No unassigned parcel available."}

        parcel_id, x, y = unassigned_parcel
        
        building_type, building_variant = determine_building_type(total_amount)
        building_info = get_building_info(building_type)
        
        # SHOULD NEVER enter this condition as we already check this in our determine_building_type function
        if not building_type or not building_variant or not building_info:
            log_message(f"Unable to determine building type or variant for amount {total_amount}")
            return {"success": False, "message": "Error assigning the parcel."}

        # Check if the maximum number of this building type has been reached
        cursor.execute('''
            SELECT COUNT(*) 
            FROM parcels 
            WHERE building_type = ?
        ''', (building_type,))
        current_count = cursor.fetchone()[0]
        
        if building_info['max_count'] is not None and current_count >= building_info['max_count']:
            return {"success": False, "message": f"The maximum number of buildings of type {building_type} has been reached."}

        fee_amount = building_info['fee_amount']
        fee_frequency = building_info['fee_frequency']
        next_fee_date = current_time + (fee_frequency * 24 * 60 * 60)

        cursor.execute("""
            UPDATE parcels
            SET owner_address = ?, building_type = ?, building_variant = ?, 
                purchase_amount = ?, purchase_date = ?, last_fee_payment = ?, 
                last_fee_check = ?, last_fee_amount = ?, fee_frequency = ?, next_fee_date = ?,
                energy_production = ?, energy_consumption = ?, zkaspa_production = ?,
                zkaspa_balance = ?, is_for_sale = ?, sale_price = ?,
                type = ?, rarity = ?
            WHERE id = ?
        """, (from_address, building_type, building_variant, total_amount, current_time, 
            current_time, current_time, fee_amount, fee_frequency, next_fee_date,
            building_info['energy_production'], building_info['energy_consumption'],
            building_info['zkaspa_production'], 0, False, None,
            'grass', None, parcel_id))

        conn.commit()

        # Check that the update was successful
        cursor.execute("SELECT * FROM parcels WHERE id = ?", (parcel_id,))
        updated_parcel = cursor.fetchone()
        if updated_parcel is None:
            raise Exception("Unable to retrieve updated parcel after update")

        result = {
            "success": True,
            "message": f"Parcel {parcel_id} assigned with a building of type {building_type} (variant {building_variant}) at coordinates ({x}, {y}).",
            "x": x,
            "y": y,
            "id": parcel_id,
            "building_type": building_type,
            "building_variant": building_variant,
            "energy_production": building_info['energy_production'],
            "energy_consumption": building_info['energy_consumption'],
            "zkaspa_production": building_info['zkaspa_production']
        }
        log_message(f"Parcel {parcel_id} assigned to {from_address}: {total_amount} KAS, type {building_type}, variant {building_variant}, coords ({x}, {y}), energy prod/cons {building_info['energy_production']}/{building_info['energy_consumption']}, zkaspa prod {building_info['zkaspa_production']}, fees {fee_amount} KAS every {fee_frequency} days, next payment {format_timestamp(next_fee_date)}")
        return result

    except sqlite3.Error as e:
        conn.rollback()
        log_message(f"SQL error while processing new parcel for {from_address}: {e}")
        return {"success": False, "message": "Error assigning the parcel."}
    except Exception as e:
        conn.rollback()
        log_message(f"Unexpected error while processing new parcel for {from_address}: {e}")
        return {"success": False, "message": "Unexpected error while assigning the parcel."}

"""
get_building_info(building_type):
Retrieves information for a specific building type.

Parameters:
- building_type (str): Name of the building type

Returns:
- dict: Building characteristics or None if not found
"""
def get_building_info(building_type):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT fee_amount, fee_frequency, energy_production, energy_consumption, zkaspa_production, max_count
            FROM building_types
            WHERE name = ?
        """, (building_type,))
        result = cursor.fetchone()
        
        if result:
            # Convert the result to a dictionary for easier access
            result_dict = dict(result)
            log_message(f"Query result for {building_type}: {result_dict}")
            
            return {
                'fee_amount': result_dict['fee_amount'],
                'fee_frequency': result_dict['fee_frequency'],
                'energy_production': result_dict['energy_production'],
                'energy_consumption': result_dict['energy_consumption'],
                'zkaspa_production': result_dict['zkaspa_production'],
                'max_count': result_dict.get('max_count')  # Use .get() to handle the case where max_count doesn't exist
            }
        else:
            log_message(f"No building found for type: {building_type}")
            return None

    except sqlite3.Error as e:
        log_message(f"SQL error while retrieving building information for {building_type}: {e}")
        return None
    except Exception as e:
        log_message(f"Unexpected error while retrieving building information for {building_type}: {e}")
        return None
    finally:
        if conn:
            try:
                conn.close()
            except Exception as e:
                log_message(f"Error while closing the connection: {e}")

"""
get_recent_transactions(address, max_retries=3, retry_delay=5):
Retrieves recent transactions for an address via the Kaspa API.

Parameters:
- address (str): Kaspa address to check
- max_retries (int): Maximum number of retry attempts
- retry_delay (int): Delay between attempts in seconds

Returns:
- list: Recent transactions or empty list in case of error
"""
def get_recent_transactions(address, max_retries=3, retry_delay=5):
    url = f"{KASPA_API_BASE_URL}/addresses/{address}/full-transactions"
    params = {
        "limit": 50,
        "resolve_previous_outpoints": "light"
    }
    
    for attempt in range(max_retries):
        try:
            response = requests.get(url, params=params, timeout=50)
            response.raise_for_status()  # Raises an HTTPError for bad responses
            return response.json()
        
        except RequestException as e:
            log_message(f"Error during attempt {attempt + 1} to retrieve transactions for address {address}: {str(e)}")
            
            if attempt < max_retries - 1:
                log_message(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                log_message("Maximum number of attempts reached. Aborting transaction retrieval.")
                return []
        
        except ValueError as e:
            log_message(f"Error decoding JSON response for address {address}: {str(e)}")
            return []
        
        except Exception as e:
            log_message(f"Unexpected error while retrieving transactions for address {address}: {str(e)}")
            return []

    return []  # If we get here, all attempts have failed
"""
update_wallet_info(address, amount, tx_id, timestamp):
Updates or inserts wallet information in the database.

Parameters:
- address (str): Wallet address
- amount (float): Transaction amount
- tx_id (str): Transaction ID
- timestamp (float): Transaction timestamp

Returns:
- bool: True if successful, False otherwise
"""
def update_wallet_info(address, amount, tx_id, timestamp):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO wallets (address, total_amount, transaction_count, last_transaction_id, last_transaction_timestamp)
            VALUES (?, ?, 1, ?, ?)
            ON CONFLICT(address) DO UPDATE SET
            total_amount = total_amount + ?,
            transaction_count = transaction_count + 1,
            last_transaction_id = ?,
            last_transaction_timestamp = ?
        ''', (address, amount, tx_id, timestamp, amount, tx_id, timestamp))
        
        conn.commit()
        
        # Check that the update was successful
        cursor.execute("SELECT * FROM wallets WHERE address = ?", (address,))
        updated_wallet = cursor.fetchone()
        if updated_wallet is None:
            raise Exception(f"Unable to retrieve updated wallet for address {address}")
        
        log_message(f"Wallet successfully updated for address {address}: new total amount = {updated_wallet['total_amount']}, transaction count = {updated_wallet['transaction_count']}")
        
        return True
    
    except sqlite3.Error as e:
        log_message(f"SQLite error while updating wallet information for {address}: {e}")
        if conn:
            conn.rollback()
        return False
    
    except Exception as e:
        log_message(f"Unexpected error while updating wallet information for {address}: {e}")
        if conn:
            conn.rollback()
        return False
    
    finally:
        if conn:
            conn.close()
"""
transaction_already_processed(tx_id):
Checks if a transaction has already been processed.

Parameters:
- tx_id (str): Transaction ID to check

Returns:
- bool: True if already processed, False otherwise
"""
def transaction_already_processed(tx_id):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT 1 FROM processed_transactions WHERE transaction_id = ?", (tx_id,))
        result = cursor.fetchone()
        
        return result is not None
    
    except sqlite3.Error as e:
        log_message(f"SQLite error while checking transaction {tx_id}: {e}")
        return False  # In case of error, we assume the transaction has not been processed
    
    except Exception as e:
        log_message(f"Unexpected error while checking transaction {tx_id}: {e}")
        return False  # In case of error, we assume the transaction has not been processed
    
    finally:
        if conn:
            conn.close()
"""
format_timestamp(timestamp):
Converts a Unix timestamp to a readable date/time string (Berlin time).

Parameters:
- timestamp (float): Unix timestamp to convert

Returns:
- str: Formatted date and time string
"""
def format_timestamp(timestamp):
    utc_time = datetime.fromtimestamp(timestamp, tz=timezone.utc)
    berlin_time = utc_time.astimezone(BERLIN_TZ)
    return berlin_time.strftime("%Y-%m-%d %H:%M:%S %Z")

"""
Upgrades an existing building or updates its characteristics.

Parameters:
- conn (sqlite3.Connection): Database connection
- address (str): Owner's address
- amount (float): Upgrade or purchase amount
- is_buy_parcel (bool): Indicates if it's a purchase of another player's plot
- manage_transaction (bool): Manages the SQL transaction if True

Calculates the new total amount, determines the new building type, and updates the plot's characteristics and information. Handles differently the cases of plot purchase and normal upgrades.

Raises an exception in case of error.
"""
def upgrade_building(conn, address, amount, is_buy_parcel, current_variant=None, manage_transaction=True):
    log_message(f"upgrade_building function called for address {address} with amount {amount} KAS. First parcel: {is_buy_parcel}")
    cursor = None
    try:
        cursor = conn.cursor()
        
        if manage_transaction:
            conn.execute("BEGIN TRANSACTION")
        
        cursor.execute("SELECT * FROM parcels WHERE owner_address = ?", (address,))
        parcel = cursor.fetchone()
        
        if not parcel:
            if manage_transaction:
                conn.rollback()
            log_message(f"No parcel found for address {address}")
            return {"success": False, "message": "Parcel not found for this address"}
        
        current_type = parcel['building_type']
        current_variant = parcel['building_variant']
        
        if is_buy_parcel:
            new_total_amount = amount
        else:
            new_total_amount = parcel['purchase_amount'] + amount
        
        log_message(f"Current parcel details: Type: {current_type}, Variant: {current_variant}, Total amount: {new_total_amount} KAS")

        cursor.execute('''
            SELECT name, min_amount, max_amount, max_count, 
                   fee_amount, fee_frequency, energy_production, energy_consumption, zkaspa_production
            FROM building_types
            ORDER BY min_amount DESC
        ''')
        available_buildings = cursor.fetchall()
        
        log_message(f"Available buildings: {[b['name'] for b in available_buildings]}")

        new_type = None
        building_info = None
        
        try:
            for building in available_buildings:
                log_message(f"Checking building: {building['name']}")
                log_message(f"  min_amount: {building['min_amount']}, type: {type(building['min_amount'])}")
                log_message(f"  max_amount: {building['max_amount']}, type: {type(building['max_amount'])}")
                log_message(f"  max_count: {building['max_count']}, type: {type(building['max_count'])}")
                
                if new_total_amount >= building['min_amount']:
                    log_message("min_amount condition verified")
                    
                    # Check max_count if applicable
                    if building['max_count'] is not None:
                        cursor.execute('SELECT COUNT(*) FROM parcels WHERE building_type = ?', (building['name'],))
                        count = cursor.fetchone()[0]
                        if count >= building['max_count']:
                            log_message(f"max_count limit reached for {building['name']}")
                            continue
                    
                    new_type = building['name']
                    building_info = dict(building)
                    log_message(f"Selected building: {new_type}")
                    break  # Exit the loop as soon as we find an appropriate building
                else:
                    log_message("min_amount condition not verified")

            if not new_type:
                log_message(f"No new building type available. Keeping current type: {current_type}")
                new_type = current_type
                cursor.execute('SELECT * FROM building_types WHERE name = ?', (current_type,))
                building_info = dict(cursor.fetchone())

            log_message(f"New selected building type: {new_type}")

        except Exception as e:
            log_message(f"Unexpected error while selecting building type: {e}")
            return {"success": False, "message": "Error while selecting building type"}

        try:
            new_fee_amount = building_info['fee_amount']
            new_fee_frequency = building_info['fee_frequency']
            new_energy_production = building_info['energy_production']
            new_energy_consumption = building_info['energy_consumption']
            new_zkaspa_production = building_info['zkaspa_production']
        except KeyError as e:
            log_message(f"Missing key in building_info: {e}")
            return {"success": False, "message": "Incomplete building information"}
        except Exception as e:
            log_message(f"Unexpected error while extracting building information: {e}")
            return {"success": False, "message": "Error while extracting building information"}

        current_time = datetime.now().timestamp()
        new_next_fee_date = current_time + (new_fee_frequency * 24 * 60 * 60)
        
        # Sélection de la nouvelle variante
        cursor.execute("SELECT variant, probability FROM building_variants WHERE building_type = ?", (new_type,))
        variants = cursor.fetchall()
        
        variant_names = [v['variant'] for v in variants]
        probabilities = [v['probability'] for v in variants]
        
        if current_variant and current_variant in variant_names:
            new_variant = current_variant
            log_message(f"Building type: {new_type}. Variant '{new_variant}' retained from previous owner.")
        else:
            # Sélectionner une nouvelle variante en fonction des probabilités
            new_variant = random.choices(variant_names, weights=probabilities, k=1)[0]
            log_message(f"Building type: {new_type}. New variant '{new_variant}' selected.")

        if new_type != current_type:
            log_message(f"Building type change: {current_type} -> {new_type}")
        else:
            log_message(f"Building type unchanged: {current_type}")

        cursor.execute("""
            UPDATE parcels
            SET building_type = ?, building_variant = ?, purchase_amount = ?,
                last_fee_amount = ?, fee_frequency = ?, next_fee_date = ?,
                last_fee_payment = ?,
                energy_production = ?, energy_consumption = ?, zkaspa_production = ?
            WHERE owner_address = ?
        """, (new_type, new_variant, new_total_amount, new_fee_amount, new_fee_frequency, new_next_fee_date,
            current_time, new_energy_production, new_energy_consumption, new_zkaspa_production, address))
        
        if cursor.rowcount == 0:
            raise Exception("Parcel update failed")
        
        if manage_transaction:
            conn.commit()
        
        log_message(f"Building upgrade for address {address}:")
        log_message(f"  Old type: {current_type} (variant {current_variant})")
        log_message(f"  New type: {new_type} (variant {new_variant})")
        log_message(f"  New purchase amount: {new_total_amount}")
        log_message(f"  New fees: {new_fee_amount} KAS every {new_fee_frequency} days")
        log_message(f"  New energy production: {new_energy_production}")
        log_message(f"  New energy consumption: {new_energy_consumption}")
        log_message(f"  New zkaspa production: {new_zkaspa_production}")
        log_message(f"  Last fee payment date: {datetime.fromtimestamp(current_time).strftime('%Y-%m-%d %H:%M:%S')}")
        log_message(f"  Next fee date: {datetime.fromtimestamp(new_next_fee_date).strftime('%Y-%m-%d %H:%M:%S')}")
        
        return {
            "success": True,
            "message": f"Building upgraded from {current_type} (variant {current_variant}) to {new_type} (variant {new_variant}).",
            "x": parcel['x'],
            "y": parcel['y'],
            "new_building_type": new_type,
            "new_building_variant": new_variant,
            "new_fee_amount": new_fee_amount,
            "new_fee_frequency": new_fee_frequency,
            "new_next_fee_date": new_next_fee_date,
            "new_energy_production": new_energy_production,
            "new_energy_consumption": new_energy_consumption,
            "new_zkaspa_production": new_zkaspa_production,
            "new_purchase_amount": new_total_amount
        }
    
    except sqlite3.Error as e:
        if manage_transaction:
            conn.rollback()
        log_message(f"SQLite error while upgrading building for address {address}: {e}")
        return {"success": False, "message": "Database error during upgrade"}
    
    except Exception as e:
        if manage_transaction:
            conn.rollback()
        log_message(f"Unexpected error while upgrading building for address {address}: {e}")
        return {"success": False, "message": "Unexpected error during upgrade"}
    
    finally:
        if cursor:
            cursor.close()
            
"""
check_all_fees():
Checks all plots for due fees and resets those unpaid after the grace period.
"""
def check_all_fees():
    log_message("check_all_fees function called.")
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Start a transaction
        conn.execute("BEGIN TRANSACTION")
        
        current_time = datetime.now().timestamp()
        
        # Retrieve all parcels with overdue payments
        cursor.execute("""
            SELECT p.id, p.owner_address, p.building_type, p.last_fee_payment, p.next_fee_date,
                   b.fee_amount, b.fee_frequency
            FROM parcels p
            JOIN building_types b ON p.building_type = b.name
            WHERE p.next_fee_date < ?
        """, (current_time,))
        
        overdue_parcels = cursor.fetchall()
        
        parcels_reset = 0
        parcels_grace_period = 0
        
        for parcel in overdue_parcels:
            parcel_id = parcel['id']
            address = parcel['owner_address']
            building_type = parcel['building_type']
            fee_amount = parcel['fee_amount']
            fee_frequency = parcel['fee_frequency']
            
            grace_period_end = parcel['next_fee_date'] + timedelta(days=GRACE_PERIOD_DAYS).total_seconds()
            
            if not GRACE_PERIOD_ENABLED or current_time > grace_period_end:
                # Reset the parcel
                cursor.execute("""
                    UPDATE parcels
                    SET owner_address = NULL, building_type = NULL, building_variant = NULL, 
                        purchase_amount = NULL, purchase_date = NULL, 
                        last_fee_payment = NULL, last_fee_check = NULL,
                        last_fee_amount = NULL, fee_frequency = NULL, next_fee_date = NULL,
                        energy_production = 0, energy_consumption = 0,
                        zkaspa_production = 0, zkaspa_balance = 0,
                        is_special = 0, is_for_sale = 0, sale_price = NULL, rarity = NULL
                    WHERE id = ?
                """, (parcel_id,))
                
                if cursor.rowcount == 1:
                    parcels_reset += 1
                    log_message(f"Parcel {parcel_id} reset for address: {address} due to non-payment of fees.")
                else:
                    log_message(f"Error while resetting parcel {parcel_id} for address: {address}")

                # Then, delete the entry from the wallets table
                cursor.execute("""
                    DELETE FROM wallets
                    WHERE address = ?
                """, (address,))
                
                if cursor.rowcount == 1:
                    log_message(f"Wallet entry deleted for address: {address}")
                else:
                    log_message(f"No wallet entry found or error while deleting for address: {address}")
            
            elif GRACE_PERIOD_ENABLED:
                # Update the last fee check
                cursor.execute("""
                    UPDATE parcels
                    SET last_fee_check = ?,
                        last_fee_amount = ?
                    WHERE id = ?
                """, (current_time, fee_amount, parcel_id))
                
                if cursor.rowcount == 1:
                    parcels_grace_period += 1
                    log_message(f"Parcel {parcel_id} (address: {address}) in grace period. Amount due: {fee_amount} KAS")
                else:
                    log_message(f"Error while updating parcel {parcel_id} for address: {address}")
        
        conn.commit()
        log_message(f"Fee check completed. {parcels_reset} parcels reset, {parcels_grace_period} in grace period.")

    except sqlite3.Error as e:
        log_message(f"SQLite error during fee check: {e}")
        if conn:
            conn.rollback()
    
    except Exception as e:
        log_message(f"Unexpected error during fee check: {e}")
        if conn:
            conn.rollback()
    
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
  
"""
is_kasland_full():
Checks if all plots in KasLand are occupied.

Returns:
- bool: True if KasLand is full, False otherwise
"""
def is_kasland_full():
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM parcels")
        total_parcels = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM parcels WHERE owner_address IS NOT NULL")
        occupied_parcels = cursor.fetchone()[0]
        
        return total_parcels == occupied_parcels

    except Exception as e:
        log_message(f"Error while checking if Kasland is full: {e}")
        return False  # By default, we consider Kasland not full in case of an error
    
    finally:
        if conn:
            conn.close()
"""
generate_random_event():
Randomly generates events affecting energy and zkaspa production.
"""
def generate_random_event():
    conn = None
    try:
        current_time = time.time()
        event_duration = 24 * 60 * 60  # 24 hours in seconds

        total_event_chance = 0.25  # 25% chance that an event will occur

        events = [
            {
                "type": "solar_flare",
                "description": "A solar flare has caused a general blackout! Energy production is interrupted for 24 hours.",
                "probability": 0.05, 
                "energy_multiplier": 0.0,
                "zkaspa_multiplier": 1
            },
            {
                "type": "maintenance",
                "description": "Electrical grid maintenance in progress. Energy production is reduced by 75% for 24 hours.",
                "probability": 0.1, 
                "energy_multiplier": 0.25,
                "zkaspa_multiplier": 1
            },
            {
                "type": "energy_surge",
                "description": "Power surge! Some lines are damaged. Energy production is reduced by 50% for 24 hours.",
                "probability": 0.1,
                "energy_multiplier": 0.5,
                "zkaspa_multiplier": 1
            },
            {
                "type": "windy_weather",
                "description": "Strong winds boost wind turbine production! Energy production is increased by 25% for 24 hours.",
                "probability": 0.1,
                "energy_multiplier": 1.25,  
                "zkaspa_multiplier": 1
            },
            {
                "type": "power_failure",
                "description": "A major power outage! Energy production drops by 80% for 24 hours.",
                "probability": 0.1,
                "energy_multiplier": 0.2,
                "zkaspa_multiplier": 1
            },
            {
                "type": "natural_disaster",
                "description": "A natural disaster strikes! Energy and zkaspa production is reduced by 75% for 24 hours.",
                "probability": 0.05,
                "energy_multiplier": 0.25,
                "zkaspa_multiplier": 0.25  
            },
            {
                "type": "mining_difficulty_spike",
                "description": "Sudden increase in mining difficulty! Zkaspa production decreases by 60% for 24 hours.",
                "probability": 0.08,
                "energy_multiplier": 1,
                "zkaspa_multiplier": 0.4
            },
            {
                "type": "technical_glitch",
                "description": "A critical bug in mining software reduces zkaspa production by 50% for 24 hours.",
                "probability": 0.08,
                "energy_multiplier": 1,
                "zkaspa_multiplier": 0.5
            },
            {
                "type": "economic_crisis",
                "description": "A severe economic crisis hits the crypto market! Zkaspa production falls by 70% for 24 hours.",
                "probability": 0.05,
                "energy_multiplier": 1,
                "zkaspa_multiplier": 0.3
            },
            {
                "type": "mining_hardware_shortage",
                "description": "Global shortage of mining hardware components! Zkaspa production decreases by 45% for 24 hours.",
                "probability": 0.06,
                "energy_multiplier": 1,
                "zkaspa_multiplier": 0.55
            }
        ]

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT * FROM events 
            WHERE end_time > ?
        ''', (current_time,))

        existing_event = cursor.fetchone()

        if existing_event:
            log_message("An event is already in progress. No new event generated.")
            return

        # Calculate the total event probability (sum of weights)
        total_event_weight = sum(event['probability'] for event in events)

        # Determine if an event occurs
        if random.random() < total_event_chance:
            # Select an event based on relative weights
            event_weights = [event['probability'] / total_event_weight for event in events]
            selected_event = random.choices(events, weights=event_weights, k=1)[0]

            # Insert the selected event into the database
            cursor.execute('''
                INSERT INTO events (event_type, start_time, end_time, description, energy_multiplier, zkaspa_multiplier)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (selected_event['type'], current_time, current_time + event_duration, selected_event['description'], 
                  selected_event['energy_multiplier'], selected_event['zkaspa_multiplier']))
            
            conn.commit()
            log_message(f"New event generated: {selected_event['type']}")
            return
        else:
            log_message("No new event generated today.")

    except Exception as e:
        if conn:
            conn.rollback()
        log_message(f"Error while generating a random event: {e}")

    finally:
        if conn:
            conn.close()
            
"""
get_current_event_effects(log_execution=True):
Retrieves the effects of the current event in the game.

Parameters:
- log_execution (bool): Activates logging if True

Returns:
- dict: Current energy and zkaspa multipliers
"""
def get_current_event_effects(log_execution=True):
    if log_execution:
        log_message("get_current_event_effects function called.")
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        current_time = time.time()
        cursor.execute('''
            SELECT event_type, energy_multiplier, zkaspa_multiplier
            FROM events 
            WHERE ? BETWEEN start_time AND end_time
            ORDER BY start_time DESC
            LIMIT 1
        ''', (current_time,))
        
        current_event = cursor.fetchone()
        
        if current_event:
            return {
                "event_type": current_event['event_type'],
                "energy_multiplier": current_event['energy_multiplier'],
                "zkaspa_multiplier": current_event['zkaspa_multiplier']
            }
        else:
            return {
                "event_type": None,
                "energy_multiplier": 1.0,
                "zkaspa_multiplier": 1.0
            }
    
    except Exception as e:
        log_message(f"Error while retrieving current event effects: {e}")
        return {
            "event_type": None,
            "energy_multiplier": 1.0,
            "zkaspa_multiplier": 1.0
        }
    
    finally:
        if conn:
            conn.close()

"""
Calculates the predicted zkaspa and energy production.

Parameters:
- conn: Database connection (optional)
- cursor: Database cursor (optional)
- log_execution (bool): Activates logging if True

Returns:
- dict: Production details

Takes into account random events and bonuses specific to certain building types (like the bonus for wind turbines).
"""
def calculate_production(conn=None, cursor=None, log_execution=True):
    if log_execution:
        log_message("calculate_production function called")
    try:
        event_effects = get_current_event_effects(log_execution=False)
        energy_multiplier = event_effects['energy_multiplier']
        zkaspa_multiplier = event_effects['zkaspa_multiplier']

        # Retrieve details for each building type
        cursor.execute(f'''
            SELECT 
                building_type,
                COUNT(*) as count,
                SUM(CASE WHEN energy_production IS NOT NULL THEN energy_production ELSE 0 END) as energy_production,
                SUM(CASE WHEN energy_consumption IS NOT NULL THEN energy_consumption ELSE 0 END) as energy_consumption,
                SUM(CASE 
                    WHEN building_type LIKE 'wind_turbine%' THEN zkaspa_production * {WIND_TURBINE_BONUS}
                    WHEN zkaspa_production IS NOT NULL THEN zkaspa_production 
                    ELSE 0 
                END) as zkaspa_production
            FROM parcels
            WHERE building_type IS NOT NULL
            GROUP BY building_type
        ''')

        building_details = cursor.fetchall()

        total_energy_production = 0
        total_energy_consumption = 0
        total_zkaspa_production = 0
        if log_execution:
            log_message("Production details by building type:")
        for building in building_details:
            b_type = building['building_type']
            count = building['count']
            energy_prod = building['energy_production']
            energy_cons = building['energy_consumption']
            zkaspa_prod = building['zkaspa_production']

            adjusted_energy_prod = energy_prod * energy_multiplier
            adjusted_zkaspa_prod = zkaspa_prod * energy_multiplier * zkaspa_multiplier

            total_energy_production += adjusted_energy_prod
            total_energy_consumption += energy_cons
            total_zkaspa_production += adjusted_zkaspa_prod
            if log_execution:
                log_message(f"  {b_type} (x{count}): Energy prod: {adjusted_energy_prod:.2f}, "
                            f"Energy cons: {energy_cons:.2f}, zkaspa prod: {adjusted_zkaspa_prod:.2f}")

        # Check if there's an energy deficit and adjust zkaspa production accordingly
        if total_energy_production < total_energy_consumption:
            total_zkaspa_production = 0
            if log_execution:
                log_message("Energy deficit detected. zkaspa production set to zero.")

        if log_execution:
            log_message(f"Total production: Energy: {total_energy_production:.2f}, "
                        f"Consumption: {total_energy_consumption:.2f}, zkaspa: {total_zkaspa_production:.2f}")
            log_message(f"Current event: {event_effects['event_type']}, "
                        f"Energy multiplier: {energy_multiplier}, zkaspa: {zkaspa_multiplier}")

        return {
            "energy_production": total_energy_production,
            "energy_consumption": total_energy_consumption,
            "zkaspa_production": total_zkaspa_production,
            "event_type": event_effects['event_type'],
            "energy_multiplier": energy_multiplier,
            "zkaspa_multiplier": zkaspa_multiplier
        }

    except Exception as e:
        log_message(f"Error during production calculation: {e}")
        return {
            "energy_production": 0,
            "energy_consumption": 0,
            "zkaspa_production": 0,
            "event_type": None,
            "energy_multiplier": 1.0,
            "zkaspa_multiplier": 1.0
        }

"""
distribute_zkaspa():
Distributes zkaspa daily to plots based on their production.

Returns:
- tuple: Distribution statistics or None in case of error
"""
def distribute_zkaspa():
    log_message("distribute_zkaspa function called.")
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Start of transaction
        conn.execute("BEGIN TRANSACTION")

        current_time = time.time()
        current_date = datetime.fromtimestamp(current_time).date()

        production = calculate_production(conn, cursor)

        log_message(f"Current event: {production['event_type']}. Energy multiplier: {production['energy_multiplier']}, zkaspa multiplier: {production['zkaspa_multiplier']}")
        log_message(f"Total production: {production['energy_production']}, Consumption: {production['energy_consumption']}")

        if production['energy_production'] >= production['energy_consumption']:
            # Distribute zkaspa to all parcels with a building
            cursor.execute(f'''
                UPDATE parcels
                SET zkaspa_balance = COALESCE(zkaspa_balance, 0) + 
                    CASE
                        WHEN building_type LIKE 'wind_turbine%' THEN COALESCE(zkaspa_production, 0) * {WIND_TURBINE_BONUS} * ? * ?
                        ELSE COALESCE(zkaspa_production, 0) * ? * ?
                    END
                WHERE building_type IS NOT NULL
            ''', (production['energy_multiplier'], production['zkaspa_multiplier'], 
                production['energy_multiplier'], production['zkaspa_multiplier']))

            rows_updated = cursor.rowcount
            if rows_updated == 0:
                log_message("No parcels updated during zkaspa distribution. This might be normal if there are no eligible parcels.")
            else:
                log_message(f"zkaspa distribution completed. {rows_updated} parcels updated.")

            log_message(f"zkaspa distribution completed. Total distributed: {production['zkaspa_production']}")

            # Consolidated statistics by building type
            cursor.execute(f'''
                SELECT 
                    building_type, 
                    COUNT(*) as count,
                    SUM(CASE
                        WHEN building_type LIKE 'wind_turbine%' THEN COALESCE(zkaspa_production, 0) * {WIND_TURBINE_BONUS} * ? * ?
                        ELSE COALESCE(zkaspa_production, 0) * ? * ?
                    END) as total_production,
                    SUM(COALESCE(zkaspa_balance, 0)) as total_balance
                FROM parcels
                WHERE building_type IS NOT NULL
                GROUP BY building_type
            ''', (production['energy_multiplier'], production['zkaspa_multiplier'], 
                production['energy_multiplier'], production['zkaspa_multiplier']))
            
            building_stats = cursor.fetchall()
            total_zkaspa = 0
            
            for stat in building_stats:
                log_message(f"Building type: {stat['building_type']}, Count: {stat['count']}, "
                            f"Total zkaspa production: {stat['total_production']}, "
                            f"Total zkaspa balance: {stat['total_balance']}")
                total_zkaspa += stat['total_balance']

            log_message(f"Total zkaspa after distribution: {total_zkaspa}")

        else:
            log_message(f"Not enough energy produced. Production: {production['energy_production']}, Consumption: {production['energy_consumption']}. No zkaspa distributed today.")
            total_zkaspa = 0  # No distribution, so total remains unchanged

        # Calculate predicted zkaspa production
        predicted_zkaspa_production = calculate_predicted_zkaspa_production()

        conn.commit()
        log_message("zkaspa distribution completed successfully.")

        # Return values for statistics saving
        return current_date, production['energy_production'], production['energy_consumption'], total_zkaspa, predicted_zkaspa_production

    except sqlite3.Error as e:
        log_message(f"SQLite error during zkaspa distribution: {e}")
        if conn:
            conn.rollback()
        return None

    except Exception as e:
        log_message(f"Unexpected error during zkaspa distribution: {e}")
        if conn:
            conn.rollback()
        return None

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

"""
calculate_predicted_zkaspa_production():
Calculates the predicted zkaspa production for the current day.

Returns:
- float: Predicted value or 0 in case of error
"""
def calculate_predicted_zkaspa_production():
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        production = calculate_production(conn, cursor)

        if production['energy_production'] >= production['energy_consumption']:
            return production['zkaspa_production']
        else:
            return 0

    except Exception as e:
        log_message(f"Error while calculating predicted zkaspa production: {e}")
        return 0

    finally:
        if conn:
            conn.close()

"""
save_daily_stats():
   Records daily statistics on energy and zkaspa production.
"""
def save_daily_stats():
    log_message("save_daily_stats function called.")
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        current_date = datetime.now().date()
        previous_date = current_date - timedelta(days=1)
        
        # Use calculate_production to get data for the previous day
        production_previous = calculate_production(conn, cursor)
        
        # Calculate total zkaspa and zkaspa production for the previous day
        cursor.execute('SELECT SUM(zkaspa_balance) as total_zkaspa FROM parcels')
        total_zkaspa = cursor.fetchone()['total_zkaspa'] or 0
        
        # Calculate zkaspa prediction for the previous day
        previous_predicted_zkaspa = calculate_predicted_zkaspa_production()
        
        # Generate a potential new event for the current day
        generate_random_event()
        
        # Recalculate production with the potential new event
        production_current = calculate_production(conn, cursor)
        
        # Calculate zkaspa prediction for the current day
        predicted_zkaspa = calculate_predicted_zkaspa_production()
        
        # Insert statistics into the database
        cursor.execute('''
            INSERT OR REPLACE INTO daily_stats
            (date, total_energy_production, total_energy_consumption, total_zkaspa, predicted_zkaspa_production, actual_zkaspa_production)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (current_date, production_previous['energy_production'], production_previous['energy_consumption'], 
              total_zkaspa, predicted_zkaspa, production_previous['zkaspa_production']))
        
        conn.commit()
        
        log_message(f"Daily statistics successfully recorded for {current_date}:")
        log_message(f"  Previous event: {production_previous['event_type']}")
        log_message(f"  Energy production (previous day): {production_previous['energy_production']}")
        log_message(f"  Energy consumption (previous day): {production_previous['energy_consumption']}")
        log_message(f"  zkaspa production (previous day): {production_previous['zkaspa_production']}")
        log_message(f"  zkaspa prediction (previous day): {previous_predicted_zkaspa}")
        log_message(f"  Current total zkaspa: {total_zkaspa}")
        log_message(f"  New generated event: {production_current['event_type']}")
        log_message(f"  zkaspa prediction for today: {predicted_zkaspa}")
        log_message(f"  Current energy multiplier: {production_current['energy_multiplier']}")
        log_message(f"  Current zkaspa multiplier: {production_current['zkaspa_multiplier']}")
        
    except Exception as e:
        if conn:
            conn.rollback()
        log_message(f"Error while recording daily statistics: {e}")
        
    finally:
        if conn:
            conn.close()

"""
process_sale_listing(conn, cursor, from_address, tx_id):
Handles listing a plot for sale or updating its price.

Parameters:
- conn: Database connection
- cursor: Database cursor
- from_address (str): Seller's address
- tx_id (str): Transaction ID

Returns:
- bool: True if the operation succeeds, False otherwise
"""
def process_sale_listing(conn, cursor, from_address, tx_id, multiplier=None):
    try:
        # Check if the parcel is already for sale
        cursor.execute("SELECT id, is_for_sale FROM parcels WHERE owner_address = ?", (from_address,))
        parcel = cursor.fetchone()
        
        if parcel:
            parcel_id = parcel['id']
            is_already_for_sale = parcel['is_for_sale']
            
            # Retrieve the total amount paid by the wallet
            cursor.execute("SELECT total_amount FROM wallets WHERE address = ?", (from_address,))
            wallet = cursor.fetchone()
            
            if wallet:

                if multiplier:
                    # Calculate sale price using the multiplier and round it
                    sale_price = round(wallet['total_amount'] * multiplier, 1)  
                else:
                    # Use the total amount paid as the sale price and round it to one decimal place
                    sale_price = round(wallet['total_amount'], 1)
                
                if is_already_for_sale:
                    # Update the sale price
                    cursor.execute("UPDATE parcels SET sale_price = ? WHERE id = ?", (sale_price, parcel_id))
                    cursor.execute("""
                        UPDATE wallets_to_monitor 
                        SET expected_amount = ?
                        WHERE address = ? AND parcel_id = ?
                    """, (sale_price, from_address, parcel_id))
                    action = "price update"
                    
                else:
                    # Mark the parcel as for sale with the calculated price
                    cursor.execute("UPDATE parcels SET is_for_sale = 1, sale_price = ? WHERE id = ?", (sale_price, parcel_id))
                    
                    # Add the seller's address to the list of addresses to monitor
                    current_time = time.time()
                    cursor.execute("""
                        INSERT INTO wallets_to_monitor (address, expected_amount, parcel_id, created_at)
                        VALUES (?, ?, ?, ?)
                    """, (from_address, sale_price, parcel_id, current_time))
                    action = "listed for sale"
                
                conn.commit()
                log_message(f"Parcel {parcel_id} {action} by {from_address} for {sale_price} KAS")
                return True
            else:
                log_message(f"No wallet information found for {from_address}")
                return False
        else:
            log_message(f"Sale listing attempt failed for {from_address}: no parcel found")
            return False
    
    except Exception as e:
        conn.rollback()
        log_message(f"Error while processing sale listing/price update: {e}")
        return False
 
"""
process_sale_cancellation(conn, cursor, from_address, tx_id):
Allows a seller to cancel the sale of their plot.

Parameters:
- conn: Database connection
- cursor: Database cursor
- from_address (str): Seller's address
- tx_id (str): Transaction ID

Returns:
- bool: True if the cancellation succeeds, False otherwise
"""
def process_sale_cancellation(conn, cursor, from_address, tx_id):
    try:
        log_message(f"Starting sale cancellation for {from_address}")
        
        # Check if the user has a parcel for sale
        cursor.execute("SELECT id, purchase_amount, building_type, building_variant FROM parcels WHERE owner_address = ? AND is_for_sale = 1", (from_address,))
        parcel = cursor.fetchone()
        
        if parcel:
            parcel_id = parcel['id']
            current_purchase_amount = parcel['purchase_amount']
            current_building_type = parcel['building_type']
            current_building_variant = parcel['building_variant']
            
            log_message(f"Parcel found: ID={parcel_id}, Purchase amount={current_purchase_amount}, Type={current_building_type}, Variant={current_building_variant}")
            
            # Cancel the sale
            cursor.execute("UPDATE parcels SET is_for_sale = 0, sale_price = NULL WHERE id = ?", (parcel_id,))
            log_message(f"Sale cancelled for parcel {parcel_id}")
            
            # Remove the wallet from the monitoring list
            cursor.execute("DELETE FROM wallets_to_monitor WHERE address = ?", (from_address,))
            log_message(f"Entry removed from wallets_to_monitor for {from_address}")
            
            # Retrieve the total invested amount
            cursor.execute("SELECT total_amount FROM wallets WHERE address = ?", (from_address,))
            wallet = cursor.fetchone()
            if wallet:
                total_amount = wallet['total_amount']
                log_message(f"Total invested amount: {total_amount}")
                
                # Check if an upgrade is needed
                new_building_type, _ = determine_building_type(total_amount)
                log_message(f"New building type determined: {new_building_type}")
                
                if new_building_type != current_building_type:
                    # Perform the upgrade
                    upgrade_result = upgrade_building(conn, from_address, total_amount - current_purchase_amount, is_buy_parcel=False, manage_transaction=False)
                    if upgrade_result['success']:
                        log_message(f"Upgrade completed: {upgrade_result['message']}")
                    else:
                        log_message(f"Upgrade failed: {upgrade_result['message']}")
                else:
                    # Update the purchase amount without changing the variant
                    cursor.execute("""
                        UPDATE parcels
                        SET purchase_amount = ?
                        WHERE id = ?
                    """, (total_amount, parcel_id))
                    log_message(f"No upgrade needed. Purchase amount updated to {total_amount} KAS.")
            else:
                log_message(f"No wallet information found for {from_address}")
            
            conn.commit()
            log_message(f"Sale cancellation successful for parcel {parcel_id}")
            return True
        else:
            log_message(f"No parcel for sale found for {from_address}")
            return False
    
    except Exception as e:
        conn.rollback()
        log_message(f"Error during sale cancellation: {str(e)}")
        log_message(f"Error type: {type(e).__name__}")
        return False

"""
Processes the purchase of a new plot by a player.

Parameters:
- conn: Database connection
- cursor: Database cursor
- buyer_address (str): Buyer's address
- new_parcel_id (int): ID of the new plot
- wallet_monitor_id (int): ID of the wallet monitor
- transaction_amount (float): Transaction amount

Handles releasing the old plot, transferring the zkaspa balance, updating the wallet, assigning the new plot, and updating the building. Calculates the upgrade amount taking into account previous purchases.

Raises an exception in case of error.
"""
def process_parcel_purchase(conn, cursor, buyer_address, new_parcel_id, wallet_monitor_id, transaction_amount):
    try:
        # Check if the buyer already owns a parcel
        cursor.execute("SELECT id, zkaspa_balance, purchase_amount FROM parcels WHERE owner_address = ?", (buyer_address,))
        existing_parcel = cursor.fetchone()

        zkaspa_to_transfer = 0
        previous_purchase_amount = 0
        is_first_parcel = existing_parcel is None

        # Retrieve the zkaspa balance of the parcel being sold
        cursor.execute("SELECT zkaspa_balance FROM parcels WHERE id = ?", (new_parcel_id,))
        sold_parcel = cursor.fetchone()
        sold_parcel_zkaspa = sold_parcel['zkaspa_balance'] if sold_parcel else 0

        if is_first_parcel:
            # For first-time buyers, give them 50% of the sold parcel's zkaspa
            zkaspa_to_transfer = sold_parcel_zkaspa * 0.5
        else:
            # For existing owners, transfer their current zkaspa balance
            zkaspa_to_transfer = existing_parcel['zkaspa_balance']
            previous_purchase_amount = existing_parcel['purchase_amount']
            
            # Free the existing parcel
            cursor.execute("""
                UPDATE parcels
                SET owner_address = NULL, building_type = NULL, building_variant = NULL,
                    purchase_amount = NULL, purchase_date = NULL, last_fee_payment = NULL,
                    last_fee_check = NULL, last_fee_amount = NULL, fee_frequency = NULL,
                    next_fee_date = NULL, energy_production = 0, energy_consumption = 0,
                    zkaspa_production = 0, zkaspa_balance = 0, is_for_sale = 0,
                    sale_price = NULL, is_special = 0, rarity = NULL
                WHERE id = ?
            """, (existing_parcel['id'],))
            log_message(f"Parcel {existing_parcel['id']} of {buyer_address} has been freed. zkaspa_balance to transfer: {zkaspa_to_transfer}")

        # Use the transaction amount as the purchase price
        sale_price = transaction_amount

        # Calculate the new total zkaspa balance
        total_zkaspa_balance = zkaspa_to_transfer

        # Update the buyer's wallet with the new total amount
        cursor.execute("""
            INSERT OR REPLACE INTO wallets (address, total_amount, transaction_count)
            VALUES (?, ?, COALESCE((SELECT transaction_count FROM wallets WHERE address = ?), 0) + 1)
            ON CONFLICT(address) DO UPDATE SET
            total_amount = ?,
            transaction_count = transaction_count + 1
        """, (buyer_address, sale_price, buyer_address, sale_price))

        # Assign the new parcel to the buyer and update the information
        cursor.execute("""
            UPDATE parcels 
            SET owner_address = ?, is_for_sale = 0, sale_price = NULL,
                zkaspa_balance = ?, purchase_amount = ?, purchase_date = ?
            WHERE id = ?
        """, (buyer_address, total_zkaspa_balance, sale_price, time.time(), new_parcel_id))

        # Update the status in wallets_to_monitor
        cursor.execute("""
            UPDATE wallets_to_monitor
            SET status = 'completed'
            WHERE id = ?
        """, (wallet_monitor_id,))

        log_message(f"Purchase confirmed for parcel {new_parcel_id}. New owner: {buyer_address}. "
                    f"New zkaspa balance: {total_zkaspa_balance}. Purchase amount: {sale_price}")

        # Récupère la variante actuelle du bâtiment de la parcelle vendue
        cursor.execute("""
            SELECT building_variant
            FROM parcels
            WHERE id = ?
        """, (new_parcel_id,))
        parcel_info = cursor.fetchone()
        current_variant = parcel_info['building_variant']

        # Calculate the amount to pass to upgrade_building
        upgrade_amount = sale_price if is_first_parcel else previous_purchase_amount + sale_price

        # Update the building based on the parcel purchase amount
        upgrade_result = upgrade_building(conn, buyer_address, upgrade_amount, is_buy_parcel=True, current_variant=current_variant, manage_transaction=False)
        if upgrade_result['success']:
            log_message(f"Building updated for parcel {new_parcel_id}: {upgrade_result['message']}")
        else:
            log_message(f"Failed to update building for parcel {new_parcel_id}: {upgrade_result['message']}")

    except Exception as e:
        log_message(f"Error while processing parcel purchase: {e}")
        raise

"""
Checks if an address has received a specific amount in the last 24 hours.

Parameters:
- address (str): Address to check
- amount (float): Expected amount
- max_retries (int): Maximum number of retry attempts
- retry_delay (int): Delay between attempts in seconds

Returns:
- tuple: (transaction found, sender address, error message)
"""
def check_and_find_transaction(address, amount, max_retries=5, retry_delay=10):
    global last_log_time
    amount_somtoshis = int(round(amount * 100000000))
    twenty_four_hours_ago = datetime.now() - timedelta(hours=24)
    #log_message(f"Searching for transaction for {address}, amount: {amount} KAS ({amount_somtoshis} somtoshis)")

    for attempt in range(max_retries):
        try:
            transactions = get_recent_transactions(address)
            #log_message(f"Attempt {attempt + 1}: {len(transactions)} transactions retrieved")
            
            for tx in transactions:
                # Convert block_time from milliseconds to seconds
                block_time_seconds = tx['block_time'] / 1000
                tx_time = datetime.fromtimestamp(block_time_seconds)
                #log_message(f"Transaction {tx['transaction_id']}: timestamp {tx_time}")
                
                if tx_time < twenty_four_hours_ago:
                    #log_message("Transaction too old, stopping processing")
                    break  # Exit the loop if the transaction is too old

                for output in tx['outputs']:
                    if output['script_public_key_address'] == address and output['amount'] == amount_somtoshis:
                        # Transaction found, look for the sender
                        if tx['inputs'] and 'previous_outpoint_address' in tx['inputs'][0]:
                            log_message(f"Transaction found for {address} with amount {amount} KAS")
                            return True, tx['inputs'][0]['previous_outpoint_address'], None
                        else:
                            log_message(f"Transaction found for {address} with amount {amount} KAS, but sender could not be identified")
                            return True, None, "Sender not identified"

            current_time = datetime.now()
            if last_log_time is None or current_time - last_log_time >= timedelta(hours=1):
                log_message(f"No matching transaction found for {address} with amount {amount} KAS")
                last_log_time = current_time
            return False, None, "No transaction found"

        except Exception as e:
            log_message(f"Error during attempt {attempt + 1} for address {address}: {str(e)}")
            log_message(f"Error type: {type(e).__name__}")

        if attempt < max_retries - 1:
            log_message(f"Retrying in {retry_delay} seconds...")
            time.sleep(retry_delay)
        else:
            log_message(f"Maximum number of attempts reached for address {address}. Aborting verification.")

    return False, None, "Verification error"

"""
Periodically checks monitored addresses for payments of plots for sale.
"""
def check_monitored_wallets():
    with app.app_context():
        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT * FROM wallets_to_monitor WHERE status = 'pending'")
            wallets_to_check = cursor.fetchall()

            for wallet in wallets_to_check:
                transaction_found, buyer_address, error_message = check_and_find_transaction(wallet['address'], wallet['expected_amount'])
                
                if transaction_found:
                    if buyer_address:
                        process_parcel_purchase(conn, cursor, buyer_address, wallet['parcel_id'], wallet['id'], wallet['expected_amount'])
                        log_message(f"Parcel purchase processed for {buyer_address}: {wallet['expected_amount']} KAS")
                    else:
                        log_message(f"Transaction found for {wallet['address']} but the buyer could not be identified")
                else:
                    # Check if the parcel is still for sale
                    cursor.execute("SELECT is_for_sale FROM parcels WHERE id = ?", (wallet['parcel_id'],))
                    is_still_for_sale = cursor.fetchone()['is_for_sale']
                    if not is_still_for_sale:
                        cursor.execute("DELETE FROM wallets_to_monitor WHERE id = ?", (wallet['id'],))
                        log_message(f"Address {wallet['address']} removed from monitoring because the parcel is no longer for sale.")

            conn.commit()

        except Exception as e:
            log_message(f"Error while checking monitored wallets: {e}")
            conn.rollback()

        finally:
            conn.close()

"""
Determines the rarity of a building variant based on its probability for front display.

Parameters:
- probability (float): Variant probability

Returns:
- str: Rarity level
"""
def determine_rarity(probability):
    if probability <= 0.001:  # ≤0.1%
        return 'Mythic'
    elif probability <= 0.01:  # 0.1-1%
        return 'Legendary'
    elif probability <= 0.05:  # 1-5%
        return 'Epic'
    elif probability <= 0.1:   # 5-10%
        return 'Rare'
    elif probability <= 0.2:   # 10-20%
        return 'Uncommon'
    elif probability <= 0.4:   # 20-40%
        return 'Common'
    else:                      # >40%
        return 'Basic'

# Configure the scheduler
executors = {
    'default': ThreadPoolExecutor(max_workers=10),
    'critical': ThreadPoolExecutor(max_workers=5),
    'minute_tasks': ThreadPoolExecutor(max_workers=2),
}

scheduler = BackgroundScheduler(executors=executors)

# Critical tasks
# 1. Check and collect fees
scheduler.add_job(func=check_all_fees, trigger="cron", hour=0, minute=0, executor='critical')
# 2. Distribute zkaspa for the ending day
scheduler.add_job(func=distribute_zkaspa, trigger="cron", hour=0, minute=1, executor='critical')
# 3. Save statistics for the day that just ended, generate a new event, and predict zkaspa production
scheduler.add_job(func=save_daily_stats, trigger="cron", hour=0, minute=2, executor='critical')
# 4. Log rotation (daily check, but effective rotation every 30 days)
scheduler.add_job(func=rotate_logs, trigger="cron", hour=0, minute=30, executor='critical')
# 5. Daily database backup
scheduler.add_job(func=backup_database, trigger="cron", hour=1, minute=0, executor='critical')

# Minute tasks
# 1. Check for new transactions (continuous task)
scheduler.add_job(func=check_new_transactions, trigger="interval", seconds=CHECK_INTERVAL, executor='minute_tasks')
# 2. Check if parcels for sale have been purchased (continuous task)
scheduler.add_job(func=check_monitored_wallets, trigger="interval", seconds=CHECK_INTERVAL, executor='minute_tasks')

scheduler.start()

##############
# API Routes
##############

# Main route: Displays the game's home page
@app.route('/')
def index():
    return render_template('index.html')

# API: Retrieves the 10 wallets with the most zkaspa
@app.route('/api/top_wallets', methods=['GET'])
def api_top_wallets():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT p.owner_address, SUM(p.zkaspa_balance) as total_zkaspa
        FROM parcels p
        WHERE p.owner_address IS NOT NULL
        GROUP BY p.owner_address
        ORDER BY total_zkaspa DESC
        LIMIT 10
    """)
    
    top_wallets = cursor.fetchall()
    conn.close()
    
    return jsonify([{'address': wallet['owner_address'], 'amount': wallet['total_zkaspa']} for wallet in top_wallets])

# API: Checks if KasLand is full or if there are available plots
@app.route('/api/kasland_status', methods=['GET'])
def api_kasland_status():
    is_full = is_kasland_full()
    return jsonify({
        "is_full": is_full,
        "message": "All plots have been sold. If you do not have a plot yet, please purchase them directly from the sellers. To do this, kindly transfer the exact amount indicated to the player's wallet address. Do not send money to the game's wallet to acquire a plot." if is_full else "Plots are available."
    })

# API: Retrieves all information about plots and map size
@app.route('/api/all_parcels', methods=['GET'])
def api_all_parcels():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Retrieve map size from the database
        cursor.execute("SELECT value FROM game_parameters WHERE key = 'map_size'")
        map_size_result = cursor.fetchone()
        if map_size_result:
            map_size = int(map_size_result[0])
        else:
            log_message("Map size not found in game_parameters")
            map_size = MAP_SIZE  # Use the default value defined globally
        
        # Get the current count for each building type
        cursor.execute("""
            SELECT building_type, COUNT(*) as count
            FROM parcels
            WHERE building_type IS NOT NULL
            GROUP BY building_type
        """)
        building_counts = {row['building_type']: row['count'] for row in cursor.fetchall()}

        # Get max_count for each building type
        cursor.execute("SELECT name, max_count FROM building_types")
        max_counts = {row['name']: row['max_count'] for row in cursor.fetchall()}
        
        # Updated query to include all new columns
        cursor.execute("""
            SELECT id, owner_address, building_type, building_variant, purchase_amount, x, y,
                purchase_date, last_fee_payment, last_fee_check, last_fee_amount, fee_frequency,
                next_fee_date, energy_production, energy_consumption, zkaspa_production, zkaspa_balance,
                is_for_sale, sale_price, type, rarity
            FROM parcels
        """)
        parcels = cursor.fetchall()
        
        result = {
            "map_size": map_size,
            "parcels": [{
                "id": parcel['id'],
                "owner_address": parcel['owner_address'],
                "building_type": parcel['building_type'],
                "building_variant": parcel['building_variant'],
                "purchase_amount": parcel['purchase_amount'],
                "x": parcel['x'],
                "y": parcel['y'],
                "purchase_date": parcel['purchase_date'],
                "last_fee_payment": parcel['last_fee_payment'],
                "last_fee_check": parcel['last_fee_check'],
                "last_fee_amount": parcel['last_fee_amount'],
                "fee_frequency": parcel['fee_frequency'],
                "next_fee_date": parcel['next_fee_date'],
                "energy_production": parcel['energy_production'],
                "energy_consumption": parcel['energy_consumption'],
                "zkaspa_production": parcel['zkaspa_production'],
                "zkaspa_balance": parcel['zkaspa_balance'],
                "is_for_sale": parcel['is_for_sale'],
                "sale_price": parcel['sale_price'],
                "type": parcel['type'],
                "rarity": determine_rarity(next(
                    (v[1] for v in next(
                        (b['variants'] for b in BUILDING_TYPES if b['name'] == parcel['building_type']), 
                        []
                    ) if v[0] == parcel['building_variant']), 
                    1.0
                )) if parcel['building_type'] and parcel['building_variant'] else 'Unknown',
                "current_count": building_counts.get(parcel['building_type'], 0),
                "max_count": max_counts.get(parcel['building_type'])
            } for parcel in parcels]
        }
        
        return jsonify(result)

    except sqlite3.Error as e:
        log_message(f"SQLite error in api_all_parcels: {e}")
        return jsonify({"error": "Database error"}), 500
    except Exception as e:
        log_message(f"Unexpected error in api_all_parcels: {e}")
        return jsonify({"error": "Unexpected error"}), 500
    finally:
        if conn:
            conn.close()

# API: Retrieves general information about the current game state
@app.route('/api/game_info', methods=['GET'])
def api_game_info():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Use calculate_production to get production data
    production = calculate_production(conn, cursor, log_execution=False)

    # Total number of parcels
    cursor.execute("SELECT COUNT(*) FROM parcels")
    total_parcels = cursor.fetchone()[0]
    
    # Total sum of parcel purchases
    cursor.execute("SELECT SUM(purchase_amount) FROM parcels")
    total_amount = cursor.fetchone()[0] or 0
    
    community_fund = total_amount * COMMUNITY_FUNDING_PERCENTAGE
    redistribution_amount = total_amount * REDISTRIBUTION_PERCENTAGE
    
    # Number of unique wallets owning at least one parcel
    cursor.execute("SELECT COUNT(DISTINCT owner_address) FROM parcels WHERE owner_address IS NOT NULL")
    unique_owners = cursor.fetchone()[0]
    
    # Calculate total zkaspa
    cursor.execute('SELECT SUM(zkaspa_balance) as total_zkaspa FROM parcels')
    total_zkaspa = cursor.fetchone()['total_zkaspa'] or 0
    
    # Retrieve data from 24 hours ago
    yesterday = (datetime.now().date() - timedelta(days=1)).isoformat()
    cursor.execute('SELECT * FROM daily_stats WHERE date = ?', (yesterday,))
    yesterday_stats = cursor.fetchone()
    
    conn.close()
    
    return jsonify({
        "total_parcels": total_parcels,
        "community_fund": community_fund,
        "redistribution_amount": redistribution_amount,
        "unique_owners": unique_owners,
        "total_energy_production": production['energy_production'],
        "total_energy_consumption": production['energy_consumption'],
        "total_zkaspa": total_zkaspa,
        "predicted_zkaspa_production": production['zkaspa_production'],
        "event_type": production['event_type'],
        "energy_multiplier": production['energy_multiplier'],
        "zkaspa_multiplier": production['zkaspa_multiplier'],
        "yesterday_stats": {
            "total_energy_production": yesterday_stats['total_energy_production'] if yesterday_stats else None,
            "total_energy_consumption": yesterday_stats['total_energy_consumption'] if yesterday_stats else None,
            "total_zkaspa": yesterday_stats['total_zkaspa'] if yesterday_stats else None,
            "predicted_zkaspa_production": yesterday_stats['predicted_zkaspa_production'] if yesterday_stats else None
        }
    })

# API: Retrieves statistics on energy production and consumption, as well as total zkaspa
@app.route('/api/energy_stats', methods=['GET'])
def api_energy_stats():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Use calculate_production to get production data
    production = calculate_production(conn, cursor, log_execution=False)

    cursor.execute('SELECT SUM(zkaspa_balance) as total_zkaspa FROM parcels')
    total_zkaspa = cursor.fetchone()['total_zkaspa'] or 0
    
    conn.close()
    
    return jsonify({
        "total_energy_production": production['energy_production'],
        "total_energy_consumption": production['energy_consumption'],
        "total_zkaspa": total_zkaspa,
        "predicted_zkaspa_production": production['zkaspa_production'],
        "event_type": production['event_type'],
        "energy_multiplier": production['energy_multiplier'],
        "zkaspa_multiplier": production['zkaspa_multiplier']
    })

# API: Retrieves current events in the game
@app.route('/api/current_events', methods=['GET'])
def api_current_events():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    current_time = time.time()
    
    cursor.execute('''
        SELECT id, event_type, description, end_time
        FROM events 
        WHERE ? BETWEEN start_time AND end_time
    ''', (current_time,))
    
    events = cursor.fetchall()
    
    conn.close()
    
    return jsonify([{
        "id": event['id'],
        "type": event['event_type'],
        "description": event['description'],
        "end_time": event['end_time']
    } for event in events])

# API: Retrieves information about plots currently for sale
@app.route('/api/parcels_for_sale', methods=['GET'])
def api_parcels_for_sale():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, x, y, building_type, building_variant, sale_price
        FROM parcels
        WHERE is_for_sale = 1
    """)
    
    parcels_for_sale = cursor.fetchall()
    conn.close()
    
    return jsonify([{
        'id': parcel['id'],
        'x': parcel['x'],
        'y': parcel['y'],
        'building_type': parcel['building_type'],
        'building_variant': parcel['building_variant'],
        'sale_price': parcel['sale_price']
    } for parcel in parcels_for_sale])

# Main entry point of the Flask application
if __name__ == '__main__':
    log_message("The application has started...")
    app.run(host='0.0.0.0', port=8000, debug=False)
