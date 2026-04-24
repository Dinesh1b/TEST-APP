"""Verification script for the Pro Scalable migration."""
import sys
import os
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# Ensure project root is on path
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

print("=" * 60)
print("  Q-Audit Runner -- Pro Scalable Verification")
print("=" * 60)

errors = []

# 1. Module Registry
print("\n[1] Module Registry")
try:
    from backend.models.module_registry import (
        get_all_modules, get_module_keys,
        get_flag_to_idx_map, get_idx_to_flag_map,
        get_groups,
    )
    mods = get_all_modules()
    print(f"    OK: {len(mods)} modules loaded")
    keys = get_module_keys()
    print(f"    OK: {len(keys)} MODULE_KEYS entries")
    groups = get_groups()
    print(f"    OK: {len(groups)} groups: {[g['name'] for g in groups]}")
    for m in mods:
        print(f"       [{m['idx']:2d}] {m['flag']:30s} -> {m['display']}")
except Exception as e:
    print(f"    FAIL: {e}")
    errors.append(f"Module Registry: {e}")

# 2. Database Service
print("\n[2] Database Service")
try:
    from backend.services.db import init_db, init_auth_db, DB_PATH, AUTH_DB_PATH
    print(f"    OK: DB path: {DB_PATH}")
    print(f"    OK: Auth DB path: {AUTH_DB_PATH}")
except Exception as e:
    print(f"    FAIL: {e}")
    errors.append(f"DB Service: {e}")

# 3. Auth Service
print("\n[3] Auth Service")
try:
    from backend.services.auth_service import hash_password, verify_password
    h = hash_password("testpass123")
    ok = verify_password(h, "testpass123")
    print(f"    OK: Password hash/verify: {ok}")
except Exception as e:
    print(f"    FAIL: {e}")
    errors.append(f"Auth Service: {e}")

# 4. Logger
print("\n[4] Logger")
try:
    from backend.logger import log, reset, log_buffer
    reset()
    log("test message")
    assert len(log_buffer) == 1
    reset()
    print(f"    OK: Logger works")
except Exception as e:
    print(f"    FAIL: {e}")
    errors.append(f"Logger: {e}")

# 5. Flask App Factory
print("\n[5] Flask App Factory")
try:
    from backend.app import create_app
    app = create_app()
    print(f"    OK: App created: {app.name}")
    rules = [r.rule for r in app.url_map.iter_rules() if r.rule != '/static/<path:filename>']
    print(f"    OK: {len(rules)} routes registered")
    for r in sorted(rules)[:10]:
        print(f"       {r}")
    if len(rules) > 10:
        print(f"       ... and {len(rules)-10} more")
except Exception as e:
    print(f"    FAIL: {e}")
    errors.append(f"App Factory: {e}")

# 6. Config Builder
print("\n[6] Config Builder")
try:
    from backend.services.config_builder import build_config_py
    test_cfg = {"browsername": "chrome", "environments": "QA"}
    result = build_config_py(test_cfg)
    assert "class Config:" in result
    print(f"    OK: Config builder generates valid output ({len(result)} chars)")
except Exception as e:
    print(f"    FAIL: {e}")
    errors.append(f"Config Builder: {e}")

print("\n" + "=" * 60)
if errors:
    print(f"  FAILED: {len(errors)} error(s)")
    for e in errors:
        print(f"    - {e}")
else:
    print("  ALL CHECKS PASSED!")
print("=" * 60)
