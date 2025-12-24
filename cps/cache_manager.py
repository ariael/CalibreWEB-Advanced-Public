# -*- coding: utf-8 -*-

import time
from threading import Lock
from . import logger

log = logger.create()

class CacheManager:
    _lock = Lock()
    _cache = {}
    
    # Default TTL (Time To Live) in seconds - 5 minutes
    DEFAULT_TTL = 300

    @classmethod
    def get(cls, key):
        with cls._lock:
            if key in cls._cache:
                value, expiry = cls._cache[key]
                if expiry > time.time():
                    # log.debug(f"Cache hit: {key}")
                    return value
                else:
                    # log.debug(f"Cache expired: {key}")
                    del cls._cache[key]
            return None

    @classmethod
    def set(cls, key, value, ttl=None):
        ttl = ttl or cls.DEFAULT_TTL
        expiry = time.time() + ttl
        with cls._lock:
            cls._cache[key] = (value, expiry)

    @classmethod
    def clear(cls):
        with cls._lock:
            cls._cache.clear()
            log.debug("Global cache cleared")

    @classmethod
    def delete(cls, key):
        with cls._lock:
            if key in cls._cache:
                del cls._cache[key]

    @classmethod
    def memoize(cls, ttl=None):
        def decorator(func):
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                # Simple key based on function name and arguments
                key = "{}_{}_{}".format(func.__name__, args, kwargs)
                result = cls.get(key)
                if result is None:
                    result = func(*args, **kwargs)
                    cls.set(key, result, ttl)
                return result
            return wrapper
        return decorator

cache = CacheManager
