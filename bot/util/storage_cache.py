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


def _wrap_and_store_coroutine(parent_cache, key, coroutine_func):
    async def func():
        function_result = await coroutine_func
        parent_cache[key] = function_result
        return function_result

    return func()


def _wrap_new_coroutine(function_to_wrap):
    async def new_coroutine():
        return function_to_wrap

    return new_coroutine()


# https://github.com/Rapptz/RoboDanny/blob/rewrite/cogs/utils/cache.py#L22
class ExpiringDict(dict):   # noqa: WPS600
    def __init__(self, seconds):
        self._default_expiring = seconds
        super().__init__()

    def __contains__(self, key):
        self._verify_cache_integrity()
        return super().__contains__(key)

    def __getitem__(self, key):
        self._verify_cache_integrity()
        return super().__getitem__(key)[0]

    def __setitem__(self, key, value, *, seconds=-1):  # noqa: WPS110
        if seconds < 0:
            seconds = self._default_expiring
        super().__setitem__(key, (value, time.monotonic() + seconds))

    def _verify_cache_integrity(self):
        # Have to do this in two steps...
        current_time = time.monotonic()
        to_remove = [
            key for (key, (_, time_expire)) in self.items() if current_time > time_expire
        ]
        for key in to_remove:
            self.pop(key)


def create_key(func, *args, **kwargs):
    def _true_repr(argument):
        if argument.__class__.__repr__ is object.__repr__:  # noqa: WPS609
            return '<{0.__module__}.{0.__class__.__name__}>'.format(argument.__class__)
        return repr(argument)

    key = ['{0.__module__}.{0.__name__}'.format(func)]  # noqa: WPS609
    key.extend(_true_repr(argument) for argument in args)
    for argument, argument_value in kwargs.items():
        key.append(_true_repr(argument))
        key.append(_true_repr(argument_value))
    return ':'.join(key)


# TODO remake this as a class
def cache(maxsize=64):  # noqa: C901,WPS212,WPS231
    def decorator(func):  # noqa: WPS212,WPS231
        internal_cache = LRU(maxsize)

        @wraps(func)
        def wrapper(*args, **kwargs):
            key = create_key(func, args, kwargs)
            stored_value = internal_cache.get(key, None)
            if stored_value is None:
                stored_value = func(*args, **kwargs)
                if inspect.isawaitable(stored_value):
                    return _wrap_and_store_coroutine(internal_cache, key, stored_value)
                internal_cache[key] = stored_value  # noqa: WPS529

            if asyncio.iscoroutinefunction(func):
                return _wrap_new_coroutine(stored_value)
            return stored_value

        def _invalidate(*args, **kwargs):
            key = create_key(args, kwargs)
            if key in internal_cache:
                # No other function to replicate del
                del internal_cache[key]  # noqa: WPS420,WPS529
                return True
            return False

        def _invalidate_containing(key):
            for cache_key in internal_cache.keys():
                if key in cache_key:
                    # No other function to replicate del
                    del internal_cache[cache_key]  # noqa: WPS420,WPS529

        wrapper.cache = internal_cache
        wrapper.invalidate = _invalidate
        wrapper.invalidate_containing = _invalidate_containing
        return wrapper

    return decorator
