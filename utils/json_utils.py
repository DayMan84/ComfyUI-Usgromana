# --- START OF FILE utils/json_utils.py ---
import os
import json

def load_json_file(path, default=None):
    if not os.path.exists(path):
        return default if default is not None else {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[Usgromana] Error reading {path}: {e}")
        return default if default is not None else {}

def save_json_file(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"[Usgromana] Error saving {path}: {e}")