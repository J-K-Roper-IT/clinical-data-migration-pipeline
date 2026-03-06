
import psycopg2
import pyodbc
from psycopg2 import sql as psql
from datetime import datetime
import os

log_dir = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, f"compare_rowcounts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")

def log(msg):
    print(msg)
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(msg + "\n")

src = psycopg2.connect(
    dbname="pd",
    user="postgres",
    password="test1234",
    host="192.168.175.137",
    port="5432"
)
src_cur = src.cursor()

dst = pyodbc.connect(
    "DRIVER={ODBC Driver 18 for SQL Server};"
    "SERVER=192.168.175.102;"
    "DATABASE=pd;"
    "UID=sa;"
    "PWD=KRAMg05212021!;"
    "TrustServerCertificate=yes;"
)
dst_cur = dst.cursor()

# Get all table names in public schema
src_cur.execute("""
    SELECT table_name FROM information_schema.tables
    WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
    ORDER BY table_name
""")
tables = [row[0] for row in src_cur.fetchall()]

for table in tables:
    try:
        src_cur.execute(psql.SQL("SELECT COUNT(*) FROM {}.{}").format(
            psql.Identifier("public"),
            psql.Identifier(table)
        ))
        pg_count = src_cur.fetchone()[0]
    except Exception as e:
        log(f"⚠️  Error counting rows in PostgreSQL table {table}: {e}")
        continue

    try:
        dst_cur.execute(f"SELECT COUNT(*) FROM [dbo].[{table}]")
        sql_count = dst_cur.fetchone()[0]
    except Exception as e:
        log(f"⚠️  Error counting rows in SQL Server table {table}: {e}")
        continue

    if pg_count == sql_count:
        log(f"✅ {table}: MATCHED ({pg_count} rows)")
    else:
        log(f"❌ {table}: MISMATCH (PostgreSQL: {pg_count}, SQL Server: {sql_count})")
