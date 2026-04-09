
from sqlalchemy import create_engine
import pandas as pd

engine = create_engine('postgresql://postgres:0000@localhost:5432/influBridge')


query = """
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'public'
"""

tables = pd.read_sql(query, engine)
print(" TABLES DISPONIBLES:")
for table in tables['table_name']:
    print(f"  • {table}")
    
    
    count_query = f"SELECT COUNT(*) FROM {table}"
    try:
        count = pd.read_sql(count_query, engine).iloc[0, 0]
        print(f"    → {count} lignes")
        
        
        col_query = f"SELECT column_name FROM information_schema.columns WHERE table_name = '{table}'"
        cols = pd.read_sql(col_query, engine)['column_name'].tolist()
        print(f"    → Colonnes: {', '.join(cols[:5])}...")
    except:
        print("    → Erreur de lecture")
    
    print()