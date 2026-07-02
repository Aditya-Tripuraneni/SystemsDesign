import asyncio
import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from RateLimitingAlgos.leaky_bucket import RateLimiterLeakyBucket


def test_leaky_bucket_accepts_until_capacity():
    async def scenario():
        limiter = RateLimiterLeakyBucket(capacity=2, processInterval=60)
        first = await limiter.process_request()
        second = await limiter.process_request()
        third = await limiter.process_request()
        return first, second, third

    assert asyncio.run(scenario()) == (True, True, False)


def test_leaky_bucket_drains_queue_state():
    async def scenario():
        limiter = RateLimiterLeakyBucket(capacity=2, processInterval=60)
        limiter.qSize = 1
        result = await limiter.process_request()
        return result, limiter.qSize

    assert asyncio.run(scenario()) == (True, 2)
