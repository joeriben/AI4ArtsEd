"""A coroutine run to its end from a synchronous (waitress) route: one fresh
loop per call, closed afterwards. The three stations that need it carried
this function copy for copy until 2026-10-10.
"""
import asyncio


def run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()
