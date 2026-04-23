import base64
import os

INPUT_EXCEL = r"C:\Users\dines\3D Objects\main_qexcel.xlsx"
OUTPUT_FILE = "sample_excel_data.py"

# Safety check
if not os.path.exists(INPUT_EXCEL):
    raise FileNotFoundError(f"Excel not found: {INPUT_EXCEL}")

with open(INPUT_EXCEL, "rb") as f:
    encoded = base64.b64encode(f.read()).decode("utf-8")

content = f'''# AUTO-GENERATED FILE
# Do not edit manually

_SAMPLE_EXCEL_B64 = (
    "{encoded}"
)
'''

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    f.write(content)

print("✅ Done!")
print("Generated:", OUTPUT_FILE)
print("Variable:", "_SAMPLE_EXCEL_B64")