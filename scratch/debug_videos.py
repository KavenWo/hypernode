from pathlib import Path
import os

path = Path(r"c:\Users\Kaven\desktop\hypernode\backend\data\sample_videos")
print(f"Directory: {path}")
print(f"Exists: {path.exists()}")
files = list(path.glob("*.mp4"))
print(f"Found files: {[f.name for f in files]}")
