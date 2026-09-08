from collections.abc import Awaitable, Callable


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
                    await recover()
        assert last_error
        raise last_error
