import re

pg_file = 'views_postgresql.sql'
ts_file = 'views_sqlserver_converted.sql'

def convert_pg_to_tsql(view_sql):
    v = view_sql

    # Replace casts
    v = re.sub(r"(\w+)::(\w+)", r"CAST(\1 AS \2)", v)

    # Replace pattern matching
    v = v.replace("~~", "LIKE")

    # Remove ORDER BY inside view
    v = re.sub(r"ORDER BY .*?;", ";", v, flags=re.IGNORECASE | re.DOTALL)

    # Wrap with IF EXISTS and GO
    header = re.match(r"CREATE OR REPLACE VIEW (\S+)\s+AS", v, re.IGNORECASE)
    if header:
        view_name = header.group(1)
        return (f"IF OBJECT_ID('{view_name}', 'V') IS NOT NULL\n"
                f"    DROP VIEW {view_name};\nGO\n{v}\nGO\n")
    return v

with open(pg_file) as f_in, open(ts_file, 'w') as f_out:
    buffer = ""
    for line in f_in:
        buffer += line
        if line.strip().endswith(";"):
            ts = convert_pg_to_tsql(buffer)
            f_out.write(ts + "\n")
            buffer = ""
