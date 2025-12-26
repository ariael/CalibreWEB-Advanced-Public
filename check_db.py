import sqlite3
import os

# Try to find the app.db
possible_paths = [
    'c:/GitHub/CalibreWEB/repo/app.db',
    'c:/GitHub/CalibreWEB/app.db',
]

db_path = None
for p in possible_paths:
    if os.path.exists(p):
        db_path = p
        break

if not db_path:
    print('Could not find app.db')
else:
    print(f'Found database: {db_path}')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in cursor.fetchall()]
    print(f'Tables: {tables}')
    
    # Check if author_info table exists
    if 'author_info' in tables:
        print('\nauthor_info table exists!')
        cursor.execute('SELECT COUNT(*) FROM author_info')
        count = cursor.fetchone()[0]
        print(f'Total records: {count}')
        
        if count > 0:
            cursor.execute('SELECT * FROM author_info LIMIT 5')
            print('\nSample records:')
            for row in cursor.fetchall():
                print(f'  ID: {row[0]}, AuthorID: {row[1]}')
                print(f'    Name: {row[2][:50] if row[2] else "None"}...')
                print(f'    Bio: {str(row[3])[:50] if row[3] else "None"}...')
                print(f'    Image: {row[4][:50] if row[4] else "None"}...')
                print()
    else:
        print('author_info table does NOT exist!')
    
    conn.close()
