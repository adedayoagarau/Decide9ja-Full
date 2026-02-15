import pandas as pd
from pathlib import Path

file_path = Path("/Volumes/Crucial X10/Decide9ja/decide9ja_backend/raw_data/opentreasury/2025/April/25-04-21.xlsx")
try:
    df = pd.read_excel(file_path, header=None)
    print("First 20 rows:")
    print(df.head(20))
except Exception as e:
    print(f"Error: {e}")
