import asyncio
from types import TracebackType

from fastapi import Request

from text_mate_backend.utils.logger import get_logger

logger = get_logger("cancel_on_disconnect")


async def _monitor_disconnect(request: Request, task: asyncio.Task[None]) -> None:
    logger.info("Starting disconnect monitor")
    try:
        while not task.done():
            try:
                message = await request.receive()
                if message["type"] == "http.disconnect":
                    task.cancel()
                    break
            except Exception as e:
                logger.warning(f"Error receiving message: {e}")
                break
            await asyncio.sleep(0.1)
    except asyncio.CancelledError:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in disconnect monitor: {e}")


class CancelOnDisconnect:
    def __init__(self, request: Request) -> None:
        self.request = request
        self.task: asyncio.Task[None] | None = None
        self.disconnect_monitor: asyncio.Task[None] | None = None

    async def __aenter__(self) -> "CancelOnDisconnect":
        task = asyncio.current_task()

        if task is None:
            raise RuntimeError("CancelOnDisconnect must be used within a task")

        self.disconnect_monitor = asyncio.create_task(_monitor_disconnect(self.request, task))

        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if self.disconnect_monitor is not None:
            self.disconnect_monitor.cancel()
            try:
                # Wait a short time for graceful cancellation
                await asyncio.wait_for(self.disconnect_monitor, timeout=0.1)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                # Expected when cancelling
                pass
            except Exception as e:
                logger.warning(f"Error during disconnect monitor cleanup: {e}")
            finally:
                self.disconnect_monitor = None
