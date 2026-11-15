"""支持 `python -m prompt_ledger`。"""

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
