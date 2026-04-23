import builtins
from backend.shared.excel_logger import write_log
import sys
sys.stdout.reconfigure(encoding="utf-8")

# Save original print
_original_print = builtins.print

def mirrored_print(*args, **kwargs):
    """Print to terminal + log to Excel safely."""
    text = " ".join(str(a) for a in args)

    # 1. Print normally
    _original_print(text)

    # 2. Write to Excel (NO print inside this call!)
    try:
        write_log("INFO", text)
    except Exception as e:
        _original_print("[Logging Error]", e)

# Override built-in print
builtins.print = mirrored_print
