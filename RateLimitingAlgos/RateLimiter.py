import asyncio
from asyncio import Lock


class RateLimiter:
    """Token bucket rate limiter.

    Each limiter starts with a fixed bucket capacity. Requests consume one token
    if a token is available, and a background task refills tokens at a steady
    interval until the bucket reaches capacity again.
    """

    def __init__(self, capacity=2, refill_amount=2, refill_interval=2):
        self._CAPACITY = capacity
        self.refill_amount = refill_amount
        self.refill_interval = refill_interval
        self.tokens = self._CAPACITY
        self.lock = Lock()
        self.running = False
        self.refill_task = None

    async def start(self):
        """Start the background refill loop."""
        self.running = True
        self.refill_task = asyncio.create_task(self._refill_bucket())

    async def stop(self):
        """Stop the refill loop and cancel the background task."""
        self.running = False
        if self.refill_task:
            self.refill_task.cancel()
            try:
                await self.refill_task
            except asyncio.CancelledError:
                pass

    async def _refill_bucket(self):
        """Refill tokens periodically without exceeding bucket capacity."""
        while self.running:
            await asyncio.sleep(self.refill_interval)
            async with self.lock:
                self.tokens = min(self._CAPACITY, self.tokens + self.refill_amount)

    async def process_request(self):
        """Consume one token if available and allow the request."""
        async with self.lock:
            if self.tokens > 0:
                self.tokens -= 1
                return True
            return False


class RateLimiterManager:
    """Manage one token bucket limiter per client key."""

    def __init__(self):
        self.limiters = {}
        self.lock = Lock()

    async def addUser(self, ipAddress):
        """Create a limiter for a client key if it does not already exist."""
        async with self.lock:
            if ipAddress not in self.limiters:
                limiter = RateLimiter()
                await limiter.start()
                self.limiters[ipAddress] = limiter
            return self.limiters[ipAddress]

    async def getUser(self, ipAddress):
        """Return the limiter for an existing client key."""
        async with self.lock:
            return self.limiters[ipAddress]

    async def getOrCreateUser(self, ipAddress):
        """Return an existing limiter or create a new one for the client key."""
        async with self.lock:
            if ipAddress not in self.limiters:
                limiter = RateLimiter()
                await limiter.start()
                self.limiters[ipAddress] = limiter
            return self.limiters[ipAddress]

    async def stopAll(self):
        """Stop every running limiter before shutdown."""
        async with self.lock:
            for limiter in self.limiters.values():
                await limiter.stop()
