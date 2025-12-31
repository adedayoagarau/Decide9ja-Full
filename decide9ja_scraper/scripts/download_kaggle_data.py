import kagglehub
import shutil
import os
import json
import pandas as pd
from collections import Counter
import subprocess

# Create directories
os.makedirs("data/social/twitter_2023_election", exist_ok=True)
os.makedirs("data/elections/2023_presidential_results", exist_ok=True)

print("=" * 60)
print("PART 1: Downloading Twitter Dataset")
print("=" * 60)

try:
    # Download tweets dataset
    path = kagglehub.dataset_download("gpreda/nigerian-presidential-election-2023-tweets")
    print("Downloaded to:", path)
    
    # Copy to our data folder
    dest_path = "data/social/twitter_2023_election"
    if os.path.exists(dest_path):
        shutil.rmtree(dest_path)
    shutil.copytree(path, dest_path)
    print(f"Copied to: {dest_path}")
    
    # List files
    print("\nFiles in dataset:")
    for f in os.listdir(dest_path):
        fpath = os.path.join(dest_path, f)
        size = os.path.getsize(fpath) / (1024*1024)  # MB
        print(f"  - {f} ({size:.2f} MB)")
        
except Exception as e:
    print(f"Error downloading Twitter dataset: {e}")

print("\n" + "=" * 60)
print("PART 2: Pulling EDA Notebook")
print("=" * 60)

try:
    # Pull the EDA notebook
    result = subprocess.run(
        ["kaggle", "kernels", "pull", "nimahmasuud/eda-presidential-nigeria-election-2023", "-p", "data/elections/2023_presidential_results"],
        capture_output=True, text=True
    )
    print(result.stdout)
    if result.returncode != 0:
        print(f"Kaggle CLI error: {result.stderr}")
    else:
        print("Notebook pulled successfully!")
        
    # List what we got
    print("\nFiles in elections folder:")
    for f in os.listdir("data/elections/2023_presidential_results"):
        print(f"  - {f}")
        
except Exception as e:
    print(f"Error pulling notebook: {e}")

print("\n" + "=" * 60)
print("Analysis will be performed next...")
print("=" * 60)
