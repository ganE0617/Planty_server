from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import os

load_dotenv()

# DB Config
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "your_password")
MYSQL_HOST = os.getenv("MYSQL_HOST", "db")
MYSQL_PORT = os.getenv("MYSQL_PORT", "3306")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "planty_db")

# Connect to MySQL server (without specifying a DB)
SQLALCHEMY_DATABASE_URL = f"mysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/"
engine = create_engine(SQLALCHEMY_DATABASE_URL)

# Drop database
with engine.connect() as conn:
    # conn.execute(text(f"DROP DATABASE IF EXISTS `{MYSQL_DATABASE}`"))
    # print(f"✅ Dropped database: {MYSQL_DATABASE}")
    conn.execute(text(f"CREATE DATABASE `{MYSQL_DATABASE}`"))