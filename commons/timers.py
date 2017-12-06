"""
Small timer objects.
Not to be used for anything requiring super accuracy.
"""
import time


def offsetTimer():
    """
    'Starts' a timer when called, returns a timer function that returns the
    time in seconds elapsed since the timer was started
    """
    start_time = time.monotonic()

    def time_func():
        return time.monotonic() - start_time

    return time_func


# this one's a class, the other one's a def...
class deltaTimer(object):
    """
    Starts a timer on object creation.
    When object is called, returns the time difference
    since last time object was called (or created, for the first call)
    """
    def __init__(self):
        self._newtime = time.monotonic()

    def __call__(self):
        self._newtime, self._oldtime = time.monotonic(), self._newtime
        return self._newtime - self._oldtime
