"""雙擊啟動（不開黑色視窗）。只用 Python 標準函式庫，不需要另外安裝套件。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from ts_iis_fetcher.app import main  # noqa: E402

main()
