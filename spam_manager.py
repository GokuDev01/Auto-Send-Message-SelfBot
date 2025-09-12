import asyncio
from typing import Optional

class SpamManager:
    def __init__(self, min_interval: float = 2.0):
        self.min_interval = min_interval
        self.task: Optional[asyncio.Task] = None
        self._stop_event: Optional[asyncio.Event] = None
        self.channel = None
        self.message = ""
        self.interval = 0.0
        self._lock = asyncio.Lock()

    async def _loop(self, channel, message, interval, stop_event):
        try:
            while not stop_event.is_set():
                await channel.send(message)
                await asyncio.sleep(interval)
        except Exception as e:
            print("Spam loop error:", e)

    async def start(self, channel, message, interval) -> bool:
        async with self._lock:
            if self.task and not self.task.done():
                return False
            self.channel = channel
            self.message = message
            self.interval = interval
            self._stop_event = asyncio.Event()
            self.task = asyncio.create_task(
                self._loop(channel, message, interval, self._stop_event)
            )
            return True

    async def stop(self) -> bool:
        async with self._lock:
            if not self.task or self.task.done():
                return False
            if self._stop_event:
                self._stop_event.set()
            await self.task
            self.task = None
            self._stop_event = None
            return True

    def status(self) -> str:
        if self.task and not self.task.done():
            ch = (
                f"{self.channel.guild.name}/{self.channel.name}"
                if self.channel else "Unknown"
            )
            preview = self.message[:150]
            return f"Running — interval: {self.interval}s — channel: {ch} — message: {preview!r}"
        return "Not running."
