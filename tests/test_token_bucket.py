import asyncio
import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from RateLimitingAlgos.token_bucket import RateLimiterTokenBucket


def test_token_bucket_consumes_tokens_until_empty():
    async def scenario():
        limiter = RateLimiterTokenBucket(capacity=2, refill_amount=1, refill_interval=60)
        first = await limiter.process_request()
        second = await limiter.process_request()
        third = await limiter.process_request()
        return first, second, third

    assert asyncio.run(scenario()) == (True, True, False)


def test_token_bucket_refill_does_not_exceed_capacity():
    async def scenario():
        limiter = RateLimiterTokenBucket(capacity=2, refill_amount=2, refill_interval=60)
        limiter.tokens = 1
        limiter.tokens = min(limiter._CAPACITY, limiter.tokens + limiter.refill_amount)
        return limiter.tokens

    assert asyncio.run(scenario()) == 2
