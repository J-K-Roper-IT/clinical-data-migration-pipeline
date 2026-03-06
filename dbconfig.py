# dbconfig.py
import os
from dotenv import load_dotenv

# Load the .env file from the local directory
load_dotenv()

# PostgreSQL Configuration (Source)
PG_CONFIG = {
    'host': os.getenv('PG_HOST'),
    'database': os.getenv('PG_DB'),
    'user': os.getenv('PG_USER'),
    'password': os.getenv('PG_PASS'),
    'port': os.getenv('PG_PORT', '5432')
}

# SQL Server Configuration (Destination)
# We build the string here so other scripts don't have to
SQL_CONN_STR = (
    f"DRIVER={{ODBC Driver 18 for SQL Server}};"
    f"SERVER={os.getenv('SQL_SERVER')};"
    f"DATABASE={os.getenv('SQL_DB')};"
    f"UID={os.getenv('SQL_USER')};"
    f"PWD={os.getenv('SQL_PASS')};"
    f"TrustServerCertificate=yes;"
)
