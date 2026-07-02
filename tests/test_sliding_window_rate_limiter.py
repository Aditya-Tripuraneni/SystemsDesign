import asyncio
import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from RateLimitingAlgos.slidingWindowRateLimiter import RateLimiterManagerSlidingWindow


def test_sliding_window_per_ip_allows_independent_clients():
    async def scenario():
        manager = RateLimiterManagerSlidingWindow(maxReqWindow=2, timeWindow=10)
        alice = await manager.getOrCreateUser("10.0.0.1")
        bob = await manager.getOrCreateUser("10.0.0.2")

        return [
            alice.allow_request(0),
            alice.allow_request(1),
            bob.allow_request(2),
            alice.allow_request(3),
            bob.allow_request(4),
        ]

    assert asyncio.run(scenario()) == [True, True, True, False, True]


def test_sliding_window_expires_old_requests():
    async def scenario():
        manager = RateLimiterManagerSlidingWindow(maxReqWindow=2, timeWindow=5)
        client = await manager.getOrCreateUser("10.0.0.9")
        return [
            client.allow_request(0),
            client.allow_request(1),
            client.allow_request(6),
            client.allow_request(7),
        ]

    assert asyncio.run(scenario()) == [True, True, True, True]


def test_sliding_window_rejects_when_window_is_full():
    async def scenario():
        manager = RateLimiterManagerSlidingWindow(maxReqWindow=2, timeWindow=5)
        client = await manager.getOrCreateUser("10.0.0.7")
        return [
            client.allow_request(0),
            client.allow_request(1),
            client.allow_request(2),
        ]

    assert asyncio.run(scenario()) == [True, True, False]
