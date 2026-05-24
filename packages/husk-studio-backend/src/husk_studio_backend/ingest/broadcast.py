from __future__ import annotations

import asyncio
from collections import defaultdict

# Simple per-run pub/sub. Each WebSocket subscriber gets its own bounded queue;
# slow subscribers drop oldest messages rather than blocking the publisher.

_subscribers: dict[str, set[asyncio.Queue]] = defaultdict(set)
_lock = asyncio.Lock()
_MAX_QUEUE = 500


async def subscribe(run_id: str) -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue(maxsize=_MAX_QUEUE)
    async with _lock:
        _subscribers[run_id].add(q)
    return q


async def unsubscribe(run_id: str, q: asyncio.Queue) -> None:
    async with _lock:
        subs = _subscribers.get(run_id)
        if subs is not None:
            subs.discard(q)
            if not subs:
                _subscribers.pop(run_id, None)


async def publish(run_id: str, event: dict) -> None:
    async with _lock:
        subs = list(_subscribers.get(run_id, ()))
    for q in subs:
        try:
            q.put_nowait(event)
        except asyncio.QueueFull:
            # Drop oldest to make room for the new event.
            try:
                q.get_nowait()
            except asyncio.QueueEmpty:
                pass
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                pass
