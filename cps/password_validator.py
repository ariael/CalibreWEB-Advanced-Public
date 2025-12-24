# -*- coding: utf-8 -*-

#  This file is part of calibre-web with phpBB integration.

import re
from . import config, logger

log = logger.create()


def validate_password_strength(password):
    """
    Validate password against Calibre-Web's configured password policy.
    
    Args:
        password (str): The password to validate
        
    Returns:
        tuple: (is_valid: bool, errors: list[str])
    """
    errors = []
    
    if not config.config_password_policy:
        # Password policy not enabled, accept any password
        return (True, [])
    
    # Check minimum length
    if len(password) < config.config_password_min_length:
        errors.append(f"Minimum {config.config_password_min_length} characters")
    
    # Check for digit
    if config.config_password_number and not re.search(r'\d', password):
        errors.append("At least one digit")
    
    # Check for lowercase letter
    if config.config_password_lower and not re.search(r'[a-z]', password):
        errors.append("At least one lowercase letter")
    
    # Check for uppercase letter
    if config.config_password_upper and not re.search(r'[A-Z]', password):
        errors.append("At least one uppercase letter")
    
    # Check for special character
    if config.config_password_special and not re.search(r'[^a-zA-Z0-9]', password):
        errors.append("At least one special character")
    
    is_valid = len(errors) == 0
    return (is_valid, errors)


def get_password_requirements():
    """
    Get a list of enabled password requirements for display to users.
    
    Returns:
        list[str]: List of password requirement strings
    """
    requirements = []
    
    if not config.config_password_policy:
        return []
    
    if config.config_password_min_length:
        requirements.append(f"At least {config.config_password_min_length} characters long")
    
    if config.config_password_number:
        requirements.append("At least one digit (0-9)")
    
    if config.config_password_lower:
        requirements.append("At least one lowercase letter (a-z)")
    
    if config.config_password_upper:
        requirements.append("At least one UPPERCASE letter (A-Z)")
    
    if config.config_password_special:
        requirements.append("At least one special character (!@#$%^&*...)")
    
    return requirements
