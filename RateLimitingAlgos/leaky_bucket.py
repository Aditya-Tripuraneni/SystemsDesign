import asyncio
from asyncio import Lock


class RateLimiterLeakyBucket:
    def __init__(self, capacity, processInterval):
        self._CAPACITY = capacity
        self.processInterval = processInterval
        self.qSize = 0
        self.lock = Lock()
        self.running = False
        self.leak_task = None

    async def start(self):
        self.running = True
        self.leak_task = asyncio.create_task(self._leak_bucket())

    async def stop(self):
        self.running = False
        if self.leak_task:
            self.leak_task.cancel()
            try:
                await self.leak_task
            except asyncio.CancelledError:
                pass

    async def _leak_bucket(self):
        while self.running:
            await asyncio.sleep(self.processInterval)
            async with self.lock:
                self.qSize = max(0, self.qSize - 1)

    async def process_request(self):
        async with self.lock:
            if self.qSize >= self._CAPACITY:
                return False

            self.qSize += 1
            return True


class RateLimiterManagerLeakyBucket:
    def __init__(self):
        self.limiters = {}
        self.lock = Lock()

    async def addUser(self, ipAddress):
        async with self.lock: 
            if ipAddress not in self.limiters:
                limiter = RateLimiterLeakyBucket(capacity=2, processInterval=2)
                await limiter.start()
                self.limiters[ipAddress] = limiter
            return self.limiters[ipAddress]

    async def getUser(self, ipAddress):
        async with self.lock: 
            return self.limiters[ipAddress]

    async def getOrCreateUser(self, ipAddress):
        async with self.lock:
            if ipAddress not in self.limiters:
                limiter = RateLimiterLeakyBucket(capacity=2, processInterval=2)
                await limiter.start()
                self.limiters[ipAddress] = limiter

            return self.limiters[ipAddress]
        
    async def stopAll(self):
        async with self.lock:
            for limiter in self.limiters.values():
                await limiter.stop()
