"""Compatibility imports for the old combined rate-limiter module.

Prefer importing from `token_bucket` or `leaky_bucket` directly.
"""

from RateLimitingAlgos.token_bucket import (  # noqa: F401
    RateLimiterManagerTokenBucket,
    RateLimiterTokenBucket,
)
from RateLimitingAlgos.leaky_bucket import (  # noqa: F401
    RateLimiterLeakyBucket,
    RateLimiterManagerLeakyBucket,
)
