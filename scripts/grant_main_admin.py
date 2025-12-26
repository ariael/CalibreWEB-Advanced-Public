#!/usr/bin/env python3
"""
Grant Main Admin role to a Calibre-Web user.

Usage: sudo python3 grant_main_admin.py <username>

This script must be run with sudo on the Debian server.
It grants full Main Admin (ROLE_ADMIN) permissions to the specified user.
"""

import sys
import os

# Add Calibre-Web directory to path
sys.path.insert(0, '/opt/calibre-web')

from cps import ub, constants

def main():
    if len(sys.argv) != 2:
        print("Usage: sudo python3 grant_main_admin.py <username>")
        sys.exit(1)
    
    username = sys.argv[1]
    
    # Initialize database session
    ub.init_db('/opt/calibre-web/app.db')
    
    # Find user
    user = ub.session.query(ub.User).filter_by(name=username).first()
    
    if not user:
        print(f"✗ User '{username}' not found in database")
        sys.exit(1)
    
    # Grant Main Admin role with all permissions
    user.role = constants.ROLE_ADMIN | sum(r for r in constants.ALL_ROLES.values() if r != constants.ROLE_ANONYMOUS)
    
    try:
        ub.session.commit()
        print(f"✓ {username} is now Main Admin with full permissions")
        print(f"  Role bitmask: {user.role}")
    except Exception as e:
        ub.session.rollback()
        print(f"✗ Failed to grant Main Admin role: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
