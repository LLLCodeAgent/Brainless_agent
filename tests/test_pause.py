import asyncio

from app.safety.pause import PauseController


def test_pause_controller_waits_until_resumed() -> None:
    async def scenario() -> None:
        controller = PauseController()
        controller.pause()
        waiter = asyncio.create_task(controller.wait_until_resumed())
        await asyncio.sleep(0)
        assert not waiter.done()
        controller.resume()
        await waiter
    asyncio.run(scenario())
