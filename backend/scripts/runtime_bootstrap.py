import asyncio
import logging
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def _load_bootstrap_runtime():
    from app.runtime_bootstrap import bootstrap_runtime

    return bootstrap_runtime


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(_load_bootstrap_runtime()())
