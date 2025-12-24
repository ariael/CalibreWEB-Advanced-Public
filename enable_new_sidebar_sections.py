#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Migration script to enable Series Tracker, Author Dashboard, and Language Section
for all existing users in Calibre-Web.

Run this script from the Calibre-Web directory:
    python3 enable_new_sidebar_sections.py
"""

import sqlite3
import os
import sys

# Sidebar constants
SIDEBAR_LANGUAGE = 1 << 1          # 2
SIDEBAR_SERIES_TRACKER = 1 << 18   # 262144
SIDEBAR_AUTHOR_DASHBOARD = 1 << 19 # 524288

NEW_SECTIONS = SIDEBAR_LANGUAGE | SIDEBAR_SERIES_TRACKER | SIDEBAR_AUTHOR_DASHBOARD

def main():
    # Find app.db
    db_path = os.path.join(os.path.dirname(__file__), 'app.db')
    if not os.path.exists(db_path):
        print(f"Error: Database not found at {db_path}")
        print("Please run this script from the Calibre-Web root directory.")
        sys.exit(1)
    
    print(f"Connecting to database: {db_path}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Get all users
        cursor.execute("SELECT id, name, sidebar_view FROM user")
        users = cursor.fetchall()
        
        print(f"\nFound {len(users)} users")
        print(f"Enabling sections: Language, Series Tracker, Author Dashboard")
        print(f"Bitwise OR value: {NEW_SECTIONS}\n")
        
        updated_count = 0
        for user_id, name, current_sidebar in users:
            # Enable new sections using bitwise OR
            new_sidebar = current_sidebar | NEW_SECTIONS
            
            if new_sidebar != current_sidebar:
                cursor.execute(
                    "UPDATE user SET sidebar_view = ? WHERE id = ?",
                    (new_sidebar, user_id)
                )
                print(f"✓ Updated user '{name}' (ID: {user_id}): {current_sidebar} → {new_sidebar}")
                updated_count += 1
            else:
                print(f"  User '{name}' (ID: {user_id}) already has these sections enabled")
        
        conn.commit()
        print(f"\n✓ Successfully updated {updated_count} users")
        print("Please restart Calibre-Web for changes to take effect.")
        
    except Exception as e:
        conn.rollback()
        print(f"\n✗ Error: {e}")
        sys.exit(1)
    finally:
        conn.close()

if __name__ == "__main__":
    main()
