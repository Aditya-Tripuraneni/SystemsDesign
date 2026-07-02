from collections import deque
from dataclasses import dataclass
from asyncio import Lock
from typing import Dict, List


@dataclass(frozen=True)
class IP:
    address: str


@dataclass(frozen=True)
class RequestEvent:
    timestamp: int
    ip: IP


class RateLimiterSlidingWindow:
    """Sliding-window rate limiter for a single IP.

    Each limiter keeps a deque of request timestamps for one client. Requests
    outside the current window are evicted before deciding whether the next
    request fits under the configured limit.
    """

    def __init__(self, maxReqWindow: int, timeWindow: int):
        self.maxReqWindow = maxReqWindow
        self.timeWindow = timeWindow
        self.request_window = deque()

    def allow_request(self, timestamp: int) -> bool:
        while self.request_window and timestamp - self.request_window[0] >= self.timeWindow:
            self.request_window.popleft()

        if len(self.request_window) >= self.maxReqWindow:
            return False

        self.request_window.append(timestamp)
        return True

    def process_requests(self, requests: List[int]) -> List[bool]:
        return [self.allow_request(timestamp) for timestamp in requests]


class RateLimiterManagerSlidingWindow:
    """Manage one sliding-window limiter per IP address."""

    def __init__(self, maxReqWindow: int = 2, timeWindow: int = 5):
        self.maxReqWindow = maxReqWindow
        self.timeWindow = timeWindow
        self.limiters: Dict[str, RateLimiterSlidingWindow] = {}
        self.lock = None

    async def _get_lock(self):
        if self.lock is None:
            self.lock = Lock()
        return self.lock

    async def addUser(self, ipAddress: str):
        lock = await self._get_lock()
        async with lock:
            if ipAddress not in self.limiters:
                self.limiters[ipAddress] = RateLimiterSlidingWindow(
                    self.maxReqWindow,
                    self.timeWindow,
                )
            return self.limiters[ipAddress]

    async def getUser(self, ipAddress: str):
        lock = await self._get_lock()
        async with lock:
            return self.limiters[ipAddress]

    async def getOrCreateUser(self, ipAddress: str):
        lock = await self._get_lock()
        async with lock:
            if ipAddress not in self.limiters:
                self.limiters[ipAddress] = RateLimiterSlidingWindow(
                    self.maxReqWindow,
                    self.timeWindow,
                )
            return self.limiters[ipAddress]

    async def stopAll(self):
        lock = await self._get_lock()
        async with lock:
            self.limiters.clear()
