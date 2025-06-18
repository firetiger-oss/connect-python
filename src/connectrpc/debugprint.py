import sys
from typing import Any

DISABLED = True


def debug(*args: Any) -> None:
    if not DISABLED:
        print(*args, file=sys.stderr)
