import logging
from collections.abc import Awaitable, Callable


LOGGER = logging.getLogger(__name__)


class RecoveryManager:
    def __init__(self, max_retries: int) -> None:
        self.max_retries = max_retries

    async def run(self, operation: Callable[[], Awaitable[str]], recover: Callable[[], Awaitable[None]]) -> str:
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                return await operation()
            except Exception as error:
                last_error = error
                if attempt < self.max_retries:
                    LOGGER.warning("Recovery attempt %s/%s after %s: %s", attempt + 1, self.max_retries,
                                   type(error).__name__, error)
                    await recover()
        assert last_error
        raise last_error
