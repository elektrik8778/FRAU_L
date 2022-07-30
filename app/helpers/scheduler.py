import time
import threading
from typing import Callable

def _worker(secs, function, args=[]):
    time.sleep(secs)
    function(*args)

def schedule(delay:int, function_to_run:Callable, args:list=[]):
    """
    Used to run `function_to_run` after `delay`

    Args:
        delay (int): Delay in seconds
        function_to_run (Callable): function to call after `delay`
        args (list, optional): List of args to pass to function. Defaults to [].
    """
    threading.Thread(target=_worker, args=[delay, function_to_run, args]).start()
