# Role bitmask definitions for Calibre-Web (Sync with constants.py)
from .import constants

# Based on constants.py
# ROLE_ADMIN = 1
# ROLE_DOWNLOAD = 2
# ROLE_UPLOAD = 4
# ROLE_EDIT = 8
# ROLE_PASSWD = 16
# ROLE_ANONYMOUS = 32
# ROLE_EDIT_SHELFS = 64
# ROLE_DELETE_BOOKS = 128
# ROLE_VIEWER = 256
# ROLE_LIMITED_ADMIN = 1024

ROLE_COMMON = constants.ROLE_VIEWER | constants.ROLE_DOWNLOAD | constants.ROLE_PASSWD # 274
ROLE_VIP_SYNC = ROLE_COMMON | constants.ROLE_EDIT_SHELFS # 338
ROLE_VIP_RW = ROLE_VIP_SYNC | constants.ROLE_UPLOAD | constants.ROLE_EDIT # 350
ROLE_FULL_ADMIN = constants.ADMIN_USER_ROLES # 479

def get_role_name(role_mask):
    if role_mask == 0:
        return "Pending/Waiting List"
    if constants.has_flag(role_mask, constants.ROLE_LIMITED_ADMIN):
        return "Limited Admin"
    if role_mask == constants.ADMIN_USER_ROLES:
        return "Full Admin"
    if (role_mask & ROLE_VIP_RW) == ROLE_VIP_RW:
        return "VIP (Read/Write/Sync)"
    if (role_mask & ROLE_VIP_SYNC) == ROLE_VIP_SYNC:
        return "VIP (Read/Sync)"
    if (role_mask & ROLE_COMMON) == ROLE_COMMON:
        return "Common User"
    return "Custom/Restricted"

def is_pending(role_mask):
    return role_mask == 0
