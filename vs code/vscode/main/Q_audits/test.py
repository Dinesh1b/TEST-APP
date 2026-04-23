import pandas as pd
import pyautogui
import time


# CONFIG
EXCEL_PATH = r"C:\Users\HP\Documents\input\scan.xlsx"
EXCEL_SHEET = "Sheet1"
COLUMN = "code"

# Load Excel
df = pd.read_excel(EXCEL_PATH, sheet_name=EXCEL_SHEET)

# Clean column names
df.columns = df.columns.str.strip().str.lower()

print("Columns found:", df.columns)

# Validate column
if COLUMN not in df.columns:
    print(f"❌ Column '{COLUMN}' not found in Excel")
    exit()

# Remove empty rows
df = df[df[COLUMN].notna()]

print(f"📊 Total scans: {len(df)}")

print("⏳ Switch to your input field in 5 seconds...")
time.sleep(5)

# FAILSAFE (move mouse to top-left to stop)
pyautogui.FAILSAFE = True

for i, row in df.iterrows():

    # 🔥 Press ESC to stop anytime
    if pyautogui.position() == (0, 0):
        print("⛔ Stopped by user")
        break

    code = str(row[COLUMN]).strip()

    if not code:
        continue

    print(f"[{i}] Scanning: {code}")

    # TYPE like scanner
    pyautogui.write(code, interval=0.02)

    # ENTER (scanner behavior)
    pyautogui.press("enter")

    # Adjust delay based on UI
    time.sleep(0.2)

print("✅ Done scanning!")