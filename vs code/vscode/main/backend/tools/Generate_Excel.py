import pandas as pd
import random
import string

NUM_RECORDS = 200000
CHUNK_SIZE = 10000   # 10k per batch

CATEGORIES = ["Electronics", "Clothing", "Food", "Stationery", "Hardware"]
LOCATIONS = ["Chennai", "Bangalore", "Hyderabad", "Mumbai"]
TAXES = [5, 12, 18, 28]

used_codes = set()

def generate_item_code():
    return "ITM" + ''.join(random.choices(string.digits, k=8))  # increase digits

def generate_barcode():
    return ''.join(random.choices(string.digits, k=12))

file_path = r"G:\My Drive\vs code\test\generated_items.xlsx"

with pd.ExcelWriter(file_path, engine='xlsxwriter') as writer:
    
    start_row = 0

    for chunk_start in range(0, NUM_RECORDS, CHUNK_SIZE):
        data = []

        for i in range(chunk_start, min(chunk_start + CHUNK_SIZE, NUM_RECORDS)):
            category = random.choice(CATEGORIES)
            item_code = generate_item_code()

            data.append({
                "Item Category *": category,
                "Item Code *": item_code,
                "Item Name *": f"{category[:3].upper()}_ITEM_{i+1}",
                "Cost Price": round(random.uniform(100, 1000), 2),
                "Sell Price": round(random.uniform(150, 1500), 2),
                "ReorderLimit": random.randint(5, 50),
                "Tax": random.choice(TAXES),
                "Location": random.choice(LOCATIONS),
                "Barcode": generate_barcode(),
                "Tag": random.choice(["New", "Hot", "Sale", ""])
            })

        df = pd.DataFrame(data)

        df.to_excel(
            writer,
            index=False,
            startrow=start_row,
            header=(start_row == 0)
        )

        start_row += len(df)

        print(f"✅ Written {start_row} rows...")

print("🔥 Done bro! File ready")