"""Synchronous wrappers for async APIs."""

import asyncio

from ._call import call as _async_call
from ._result import Result


def _run(coro):
    """Run a coroutine synchronously.

    Handles the case where we're already inside an event loop
    (Jupyter notebooks, Streamlit).
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result()
    else:
        return asyncio.run(coro)


def call_sync(
    prompt: str,
    *,
    system: str = "",
    model: str | None = None,
    config: str | None = None,
) -> Result:
    """Synchronous version of call().

    Example::

        from liteagent import call_sync
        result = call_sync("Summarize this data", system="You are a data analyst")
        print(result)
    """
    return _run(_async_call(prompt, system=system, model=model, config=config))
