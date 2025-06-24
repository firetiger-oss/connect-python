import sys
from typing import Any

DISABLED = False


def debug(*args: Any) -> None:
    if not DISABLED:
        print(*args, file=sys.stderr)
