
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from cps import ub, constants

def update_user_preferences():
    print("Updating user preferences...")
    users = ub.session.query(ub.User).all()
    
    # Calculate mask for Series Tracker and Author Dashboard
    # SIDEBAR_SERIES_TRACKER = 1 << 18
    # SIDEBAR_AUTHOR_DASHBOARD = 1 << 19
    mask_to_add = constants.SIDEBAR_SERIES_TRACKER | constants.SIDEBAR_AUTHOR_DASHBOARD
    
    count = 0
    for user in users:
        current_view = user.sidebar_view or 0
        new_view = current_view | mask_to_add
        
        if new_view != current_view:
            user.sidebar_view = new_view
            count += 1
            print(f"Updated user: {user.name}")
            
    try:
        ub.session.commit()
        print(f"Successfully updated {count} users.")
    except Exception as e:
        ub.session.rollback()
        print(f"Error updating users: {e}")

if __name__ == "__main__":
    update_user_preferences()
