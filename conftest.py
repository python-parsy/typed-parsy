import sys
from typing import List

collect_ignore: List[str] = []

if sys.version_info < (3, 7):
    # Python 3.6 and below don't have `dataclasses`
    collect_ignore = ["examples/sql_select.py"]
