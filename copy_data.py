import time
import os
import traceback
from datetime import datetime
import dbconfig  # Import our safe config
import psycopg2
import pyodbc
from psycopg2 import sql as psql

# Setup logging
log_dir = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, f"log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")

def log(message):
    print(message)
    with open(log_file, "a", encoding="utf-8") as logf:
        logf.write(message + "\n")

# --- STEP 1: DROP/CREATE DATABASE (SQL SERVER) ---
# Note: Using dbconfig to get master connection parameters
master_conn_str = dbconfig.SQL_CONN_STR.replace(f"DATABASE={os.getenv('SQL_DB')}", "DATABASE=master")
master_conn = pyodbc.connect(master_conn_str, autocommit=True)
master_cur = master_conn.cursor()

master_cur.execute(f"IF EXISTS (SELECT name FROM sys.databases WHERE name = '{os.getenv('SQL_DB')}') DROP DATABASE [{os.getenv('SQL_DB')}]")
log(f"Dropped existing database if it existed.")
time.sleep(2)
master_cur.execute(f"CREATE DATABASE [{os.getenv('SQL_DB')}]")
log(f"Created new database.")
time.sleep(2)
master_cur.close()
master_conn.close()

# --- STEP 2: ESTABLISH SANITIZED CONNECTIONS ---
# PostgreSQL Source
src = psycopg2.connect(**dbconfig.PG_CONFIG)
src.autocommit = True
src_cur = src.cursor()

# SQL Server Destination
dst = pyodbc.connect(dbconfig.SQL_CONN_STR)
dst.autocommit = True
dst_cur = dst.cursor()
dst_cur.fast_executemany = True

# --- STEP 3: MIGRATE DATA ---
src_cur.execute("""
    SELECT table_schema, table_name
    FROM information_schema.tables
    WHERE table_type = 'BASE TABLE' AND table_schema NOT IN ('pg_catalog', 'information_schema')
""")
tables = src_cur.fetchall()
log(f"\nFound {len(tables)} tables.")

for schema, table in tables:
    log(f"\n➡️ Processing {schema}.{table}")
    target_schema = "dbo" if schema.lower() == "public" else schema

    if target_schema != "dbo":
        dst_cur.execute(f"IF SCHEMA_ID('{target_schema}') IS NULL EXEC('CREATE SCHEMA [{target_schema}]')")

    src_cur.execute(psql.SQL("SELECT column_name, data_type, character_maximum_length, numeric_precision, numeric_scale "
                             "FROM information_schema.columns WHERE table_schema = %s AND table_name = %s"),
                    (schema, table))
    columns_info = src_cur.fetchall()

    if not columns_info:
        log(f" ⚠️  No columns found in {schema}.{table}, skipping.")
        continue

    dst_cur.execute(f"IF OBJECT_ID('{target_schema}.{table}', 'U') IS NOT NULL DROP TABLE [{target_schema}].[{table}]")

    col_defs = []
    col_names = []

    for name, dtype, char_len, num_prec, num_scale in columns_info:
        col_names.append(name)
        if dtype in ('character varying', 'text', 'character'):
            col_type = f"VARCHAR({char_len})" if char_len and char_len <= 4000 else "VARCHAR(MAX)"
        elif dtype in ('integer', 'smallint'):
            col_type = "INT"
        elif dtype == 'bigint':
            col_type = "BIGINT"
        elif dtype in ('numeric', 'decimal'):
            col_type = f"DECIMAL({num_prec or 38}, {min(num_scale or 0, 5)})"
        elif dtype == 'boolean':
            col_type = "BIT"
        elif dtype in ('real', 'double precision'):
            col_type = "FLOAT"
        elif dtype == 'bytea':
            col_type = "VARBINARY(MAX)"
        elif dtype.startswith('timestamp') or dtype == 'date':
            col_type = "DATETIME2"
        else:
            col_type = "VARCHAR(MAX)"
        col_defs.append(f"[{name}] {col_type}")

    columns_sql = ", ".join(col_defs)
    dst_cur.execute(f"CREATE TABLE [{target_schema}].[{table}] ({columns_sql})")
    log(f" ↳ created table {table}")

    query = psql.SQL("SELECT {fields} FROM {schema}.{table}").format(
        fields=psql.SQL(", ").join(psql.Identifier(col) for col in col_names),
        schema=psql.Identifier(schema),
        table=psql.Identifier(table)
    )
    
    try:
        src_cur.execute(query)
        placeholders = ", ".join("?" for _ in col_names)
        dst_sql = f"INSERT INTO [{target_schema}].[{table}] ({', '.join(f'[{c}]' for c in col_names)}) VALUES ({placeholders})"

        fetch_size = 5000
        total_inserted = 0
        while True:
            rows = src_cur.fetchmany(fetch_size)
            if not rows:
                break
            try:
                dst_cur.executemany(dst_sql, rows)
                total_inserted += len(rows)
                log(f" ↳ inserted {len(rows)} rows into {table}")
            except Exception as e:
                log(f" ⚠️  Error inserting batch into {table}: {e}")
                log(traceback.format_exc())
        
        if total_inserted == 0:
            log(f" ↳ no data in table {table}")
    except Exception as e:
        log(f" ⚠️  Error querying data from {schema}.{table}: {e}")
        log(traceback.format_exc())
