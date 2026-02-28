from __future__ import annotations

import time
import threading
from collections import deque
from dataclasses import dataclass

@dataclass
class RateLimit:
    max_requests: int
    window_seconds: int
    
class SlidingWindowLimiter:
    """ 
    simple sliding window limiter
    """
    def __init__(self):
        self._lock = threading.lock()
        self._events :dict[str, deque[float] ] = {}
        
    def allow(self, key: str, limit: RateLimit) -> bool:
        now = time.time()
        cutoff = now - limit.window_seconds
        with self._lock:
            q = self._events.get(key)
            if q is None:
                q = deque()
                self._events[key] = q
            
            while q and q[0] < cutoff:
                q.popleft()
            if len(q) >= limit.max_requests:
                return False

            q.append(now)
            
class ConcurrentLimiter:
    """ 
    limits concurrent chats
    """
    def __init__(self):
        self._lock = threading.lock()
        self._sems: dict[str, threading.Semaphore] = {}
        
    def acquire(self, key:str, max_concurrent: int) -> None:
        with self._lock:
            sem = self._sems.get(key)
            if sem is None:
                sem = threading.Semaphore(max_concurrent)
                self._sems[key] = sem
        sem.acquire()
        
    def release(self, key:str) -> None:
        with self._lock:
            sem = self._sems.get(key)
        if sem:
            sem.release()
            
GLOBAL_RATE_LIMITER = SlidingWindowLimiter()
GLOBAL_CONCURRENCY = ConcurrentLimiter()
        
        