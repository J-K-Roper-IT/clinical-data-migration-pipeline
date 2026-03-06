import psycopg2
import pyodbc
from psycopg2 import sql as psql
from datetime import datetime
import os
import re

# Setup logging
log_dir = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, f"index_migration_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
error_log_file = os.path.join(log_dir, f"index_errors_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")

def log(msg, error_log=False):
    print(msg)
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(msg + "\n")
    if error_log:
        with open(error_log_file, "a", encoding="utf-8") as f:
            f.write(msg + "\n")

# Database connections
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

def get_postgresql_indexes():
    """Retrieve all indexes from PostgreSQL with detailed information"""
    query = """
    SELECT
        n.nspname AS schema_name,
        t.relname AS table_name,
        i.relname AS index_name,
        pg_get_indexdef(i.oid) AS index_definition,
        CASE WHEN x.indisprimary THEN 1 ELSE 0 END AS is_primary_key,
        CASE WHEN x.indisunique THEN 1 ELSE 0 END AS is_unique,
        am.amname AS index_type,
        pg_get_expr(x.indpred, x.indrelid) AS filter_condition,
        array_to_string(x.indkey, ' ') AS indkey,
        (SELECT array_agg(attname) 
         FROM pg_attribute 
         WHERE attrelid = x.indrelid AND attnum = ANY(x.indkey)) AS column_names,
        pg_get_constraintdef(c.oid, true) AS constraint_def
    FROM
        pg_index x
        JOIN pg_class i ON i.oid = x.indexrelid
        JOIN pg_class t ON t.oid = x.indrelid
        JOIN pg_namespace n ON n.oid = t.relnamespace
        JOIN pg_am am ON i.relam = am.oid
        LEFT JOIN pg_constraint c ON c.conindid = i.oid
    WHERE
        n.nspname NOT IN ('pg_catalog', 'information_schema')
        AND t.relkind = 'r'  -- regular tables only
    ORDER BY
        n.nspname, t.relname, i.relname;
    """
    src_cur.execute(query)
    return src_cur.fetchall()

def convert_index_definition(pg_def, is_unique, is_primary, index_type, filter_condition, 
                          schema_name, table_name, index_name, column_names):
    """Convert PostgreSQL index definition to SQL Server syntax with detailed error handling"""
    try:
        # Handle primary keys
        if is_primary:
            return None, "Primary key - handled separately"
        
        # Handle unsupported index types
        if index_type not in ['btree', 'hash']:
            return None, f"Unsupported index type: {index_type}"
        
        # Extract the columns part
        match = re.search(r'CREATE (UNIQUE )?INDEX \w+ ON \w+\.?\w+ \((.+)\)', pg_def)
        if not match:
            return None, "Could not parse index definition columns"
        
        columns = match.group(2)
        
        # Format table name with schema
        full_table_name = f"[{schema_name}].[{table_name}]"
        
        # Handle included columns (if any)
        included_cols = []
        if 'INCLUDE' in pg_def:
            include_match = re.search(r'INCLUDE \((.+?)\)', pg_def)
            if include_match:
                included_cols = [col.strip() for col in include_match.group(1).split(',')]
        
        # Handle filter conditions (partial indexes)
        where_clause = ''
        if filter_condition:
            where_clause = f" WHERE {filter_condition}"
        
        # Build SQL Server index statement
        unique = 'UNIQUE ' if is_unique else ''
        
        # Use column_names from query if available, otherwise fall back to parsing
        if column_names and len(column_names) > 0:
            columns = ', '.join([f"[{col}]" for col in column_names])
        else:
            columns = ', '.join([f"[{col.strip()}]" for col in columns.split(',')])
        
        sql = f"CREATE {unique}INDEX [{index_name}] ON {full_table_name} ({columns})"
        
        if included_cols:
            included_cols = ', '.join([f"[{col}]" for col in included_cols])
            sql += f" INCLUDE ({included_cols})"
        
        if where_clause:
            sql += where_clause
        
        return sql, "Successfully converted"
    
    except Exception as e:
        return None, f"Conversion error: {str(e)}"

def create_sql_server_index(index_name, create_statement, schema_name, table_name):
    """Create index in SQL Server with detailed error handling"""
    try:
        # Check if index already exists
        check_query = f"""
        SELECT 1 FROM sys.indexes 
        WHERE name = '{index_name}' 
        AND object_id = OBJECT_ID('[{schema_name}].[{table_name}]')
        """
        dst_cur.execute(check_query)
        if dst_cur.fetchone():
            return False, "Index already exists"
        
        # Create the index
        dst_cur.execute(create_statement)
        dst.commit()
        return True, "Successfully created"
    except pyodbc.Error as e:
        dst.rollback()
        error_msg = str(e).replace('\n', ' ').replace('\r', ' ')
        return False, f"SQL Server error: {error_msg}"

def migrate_indexes():
    """Main migration function with enhanced error tracking"""
    log("Starting index migration from PostgreSQL to SQL Server")
    log(f"Start time: {datetime.now()}")
    log("\nERROR DETAILS WILL BE WRITTEN TO SEPARATE ERROR LOG FILE\n", error_log=True)
    
    # Get all indexes from PostgreSQL
    log("Retrieving indexes from PostgreSQL...")
    indexes = get_postgresql_indexes()
    log(f"Found {len(indexes)} indexes to migrate")
    
    # Process each index
    success_count = 0
    skip_count = 0
    error_count = 0
    
    for idx in indexes:
        (schema, table, index_name, pg_def, is_primary, is_unique, 
         index_type, filter_condition, indkey, column_names, constraint_def) = idx
        
        # Log basic info about each index being processed
        log(f"\nProcessing index: {schema}.{table}.{index_name}")
        log(f"PostgreSQL definition: {pg_def}")
        
        # Skip primary keys (they're created with the table)
        if is_primary:
            msg = f"Skipping primary key {index_name} on {schema}.{table}"
            if constraint_def:
                msg += f" (constraint: {constraint_def})"
            log(msg)
            skip_count += 1
            continue
        
        # Convert index definition
        sql_def, conversion_msg = convert_index_definition(
            pg_def, is_unique, is_primary, index_type, filter_condition,
            schema, table, index_name, column_names
        )
        
        if not sql_def:
            error_msg = (f"Failed to convert index {index_name} on {schema}.{table}\n"
                       f"Reason: {conversion_msg}\n"
                       f"Original definition: {pg_def}\n"
                       f"Index type: {index_type}\n"
                       f"Filter condition: {filter_condition}\n"
                       f"Column names: {column_names}\n")
            log(error_msg, error_log=True)
            error_count += 1
            continue
        
        # Create index in SQL Server
        log(f"Attempting to create index {index_name} on {schema}.{table}")
        log(f"SQL Server definition: {sql_def}")
        
        created, creation_msg = create_sql_server_index(index_name, sql_def, schema, table)
        if created:
            log(f"Successfully created index {index_name}")
            success_count += 1
        else:
            error_msg = (f"Failed to create index {index_name} on {schema}.{table}\n"
                       f"Reason: {creation_msg}\n"
                       f"SQL Server definition attempted: {sql_def}\n")
            log(error_msg, error_log=True)
            error_count += 1
    
    # Summary
    log("\nMigration complete")
    log(f"Total indexes processed: {len(indexes)}")
    log(f"Successfully created: {success_count}")
    log(f"Skipped (primary keys): {skip_count}")
    log(f"Errors: {error_count}")
    log(f"End time: {datetime.now()}")
    
    # Write summary to error log as well
    summary = (f"\nMIGRATION SUMMARY\n"
              f"Total indexes processed: {len(indexes)}\n"
              f"Successfully created: {success_count}\n"
              f"Skipped (primary keys): {skip_count}\n"
              f"Errors: {error_count}\n")
    log(summary, error_log=True)

if __name__ == "__main__":
    migrate_indexes()
    src_cur.close()
    src.close()
    dst_cur.close()
    dst.close()
