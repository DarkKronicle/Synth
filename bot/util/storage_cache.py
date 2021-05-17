"""
This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at http://mozilla.org/MPL/2.0/.
Rapptz/RoboDanny: https://github.com/Rapptz/RoboDanny/blob/rewrite/cogs/utils/cache.py
This is a really cool way to have caching enabled for different functions. I used some of the same logic that
Rapptz did in RoboDanny.
Tutorial on how this stuff works: https://realpython.com/primer-on-python-decorators/#caching-return-values
"""
import asyncio
import inspect
import time
from functools import wraps

from lru import LRU


def _wrap_and_store_coroutine(cache, key, coro):
    async def func():
        value = await coro
        cache[key] = value
        return value

    return func()


def _wrap_new_coroutine(value):
    async def new_coroutine():
        return value

    return new_coroutine()


# https://github.com/Rapptz/RoboDanny/blob/rewrite/cogs/utils/cache.py#L22
class ExpiringDict(dict):
    def __init__(self, seconds):
        self.__ttl = seconds
        super().__init__()

    def __verify_cache_integrity(self):
        # Have to do this in two steps...
        current_time = time.monotonic()
        to_remove = [k for (k, (v, t)) in self.items() if current_time > t]
        for k in to_remove:
            del self[k]

    def __contains__(self, key):
        self.__verify_cache_integrity()
        return super().__contains__(key)

    def __getitem__(self, key):
        self.__verify_cache_integrity()
        return super().__getitem__(key)[0]

    def __setitem__(self, key, value, *, seconds=-1):
        if seconds < 0:
            seconds = self.__ttl
        super().__setitem__(key, (value, time.monotonic() + seconds))


def cache(maxsize=64):
    def decorator(func):
        _internal_cache = LRU(maxsize)

        def create_key(*args, **kwargs):
            def _true_repr(o):
                if o.__class__.__repr__ is object.__repr__:
                    return f'<{o.__class__.__module__}.{o.__class__.__name__}>'
                return repr(o)

            key = [f'{func.__module__}.{func.__name__}']
            key.extend(_true_repr(o) for o in args)
            for k, v in kwargs.items():
                key.append(_true_repr(k))
                key.append(_true_repr(v))
            return ':'.join(key)

        @wraps(func)
        def wrapper(*args, **kwargs):
            key = create_key(args, kwargs)
            if key in _internal_cache:
                value = _internal_cache[key]
            else:
                value = func(*args, **kwargs)
                if inspect.isawaitable(value):
                    return _wrap_and_store_coroutine(_internal_cache, key, value)
                _internal_cache[key] = value

            if asyncio.iscoroutinefunction(func):
                return _wrap_new_coroutine(value)
            return value

        def _invalidate(*args, **kwargs):
            key = create_key(args, kwargs)
            if key in _internal_cache:
                del _internal_cache[key]
                return True
            return False

        def _invalidate_containing(key):
            for k in _internal_cache.keys():
                if key in k:
                    del _internal_cache[k]

        wrapper.cache = _internal_cache
        wrapper.invalidate = _invalidate
        wrapper.invalidate_containing = _invalidate_containing
        return wrapper

    return decorator