import psycopg2
import pyodbc
from psycopg2 import sql as psql
from datetime import datetime
import os
import dbconfig  # Import our safe centralized config

# Setup logging
log_dir = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, f"compare_rowcounts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")

def log(msg):
    print(msg)
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(msg + "\n")

# --- SANITIZED CONNECTIONS ---
# Connect to PostgreSQL using the dictionary unpacking (**PG_CONFIG)
src = psycopg2.connect(**dbconfig.PG_CONFIG)
src_cur = src.cursor()

# Connect to SQL Server using the pre-built connection string
dst = pyodbc.connect(dbconfig.SQL_CONN_STR)
dst_cur = dst.cursor()

# --- AUDIT LOGIC ---
log(f"Starting row count audit: {datetime.now()}")

# Get all table names in public schema (PostgreSQL)
src_cur.execute("""
    SELECT table_name FROM information_schema.tables
    WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
    ORDER BY table_name
""")
tables = [row[0] for row in src_cur.fetchall()]

log(f"Auditing {len(tables)} tables...\n")

for table in tables:
    # Get Source Count (PostgreSQL)
    try:
        src_cur.execute(psql.SQL("SELECT COUNT(*) FROM {}.{}").format(
            psql.Identifier("public"),
            psql.Identifier(table)
        ))
        pg_count = src_cur.fetchone()[0]
    except Exception as e:
        log(f"⚠️  Error counting rows in PostgreSQL table {table}: {e}")
        continue

    # Get Destination Count (SQL Server)
    try:
        # Note: mapping 'public' to 'dbo' as per migration logic
        dst_cur.execute(f"SELECT COUNT(*) FROM [dbo].[{table}]")
        sql_count = dst_cur.fetchone()[0]
    except Exception as e:
        log(f"⚠️  Error counting rows in SQL Server table {table}: {e}")
        continue

    # Compare results
    if pg_count == sql_count:
        log(f"✅ {table}: MATCHED ({pg_count} rows)")
    else:
        log(f"❌ {table}: MISMATCH (PostgreSQL: {pg_count}, SQL Server: {sql_count})")

log(f"\nAudit completed: {datetime.now()}")

# Cleanup
src_cur.close()
src.close()
dst_cur.close()
dst.close()
