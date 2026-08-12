"""极简测试运行器：无 pytest 依赖，按源码定义顺序执行 test_ 开头的函数。"""
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import tests.test_app as app_tests  # noqa: E402

items = [
    (name, getattr(app_tests, name))
    for name in dir(app_tests)
    if name.startswith("test_")
]
items.sort(key=lambda item: item[1].__code__.co_firstlineno)

passed = failed = 0
for name, fn in items:
    try:
        fn()
        passed += 1
        print(f"PASS  {name}")
    except Exception:
        failed += 1
        print(f"FAIL  {name}")
        traceback.print_exc()
print(f"\n{passed} passed, {failed} failed (total {len(items)})")
sys.exit(1 if failed else 0)
