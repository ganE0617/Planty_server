import mysql.connector
from dotenv import load_dotenv
import os

load_dotenv()

# Database configuration
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "your_password")
MYSQL_HOST = os.getenv("MYSQL_HOST", "db")
MYSQL_PORT = os.getenv("MYSQL_PORT", "3306")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "planty_db")

def init_database():
    try:
        # Connect to MySQL server without specifying a database
        conn = mysql.connector.connect(
            host=MYSQL_HOST,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            port=MYSQL_PORT
        )
        cursor = conn.cursor()

        # Create database if it doesn't exist
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {MYSQL_DATABASE}")
        print(f"Database '{MYSQL_DATABASE}' created or already exists.")

        # Switch to the database
        cursor.execute(f"USE {MYSQL_DATABASE}")
        
        # Close the connection
        cursor.close()
        conn.close()
        
        print("Database initialization completed successfully!")
        
    except mysql.connector.Error as err:
        print(f"Error: {err}")
        raise

if __name__ == "__main__":
    init_database() 