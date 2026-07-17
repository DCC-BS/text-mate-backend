import asyncio
from types import TracebackType

from dcc_backend_common.logger import get_logger
from fastapi import Request

logger = get_logger("cancel_on_disconnect")


async def _monitor_disconnect(request: Request, task: asyncio.Task[None]) -> None:
    logger.debug("Starting disconnect monitor")
    try:
        while not task.done():
            try:
                message = await request.receive()
                if message["type"] == "http.disconnect":
                    task.cancel()
                    break
            except Exception:
                logger.warning("Error receiving message in disconnect monitor", exc_info=True)
                break
            await asyncio.sleep(0.1)
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("Unexpected error in disconnect monitor")


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
            except Exception:
                logger.warning("Error during disconnect monitor cleanup", exc_info=True)
            finally:
                self.disconnect_monitor = None
