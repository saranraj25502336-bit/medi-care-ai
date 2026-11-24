# ============================================
# DATABASE INITIALIZATION SCRIPT
# Run once to set up tables and seed data
# Usage: python init_db.py
# ============================================

import mysql.connector
from config import Config
import os

def init_database():
    """Initialize database with schema and seed data"""
    
    # Read the SQL file
    sql_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'database.sql')
    
    if not os.path.exists(sql_path):
        print(f"[ERROR] SQL file not found at: {sql_path}")
        return False
    
    with open(sql_path, 'r') as f:
        sql_content = f.read()
    
    try:
        # Connect without database first to create it
        conn = mysql.connector.connect(
            host=Config.DB_HOST,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            port=Config.DB_PORT
        )
        cursor = conn.cursor()
        
        # Execute the SQL (creates DB, tables, and inserts data)
        statements = sql_content.split(';')
        for statement in statements:
            if statement.strip():
                cursor.execute(statement)
        
        cursor.close()
        conn.close()
        print("[OK] Database initialized successfully!")
        return True
        
    except mysql.connector.Error as err:
        print(f"[ERROR] MySQL Error: {err}")
        return False

if __name__ == '__main__':
    init_database()
   