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
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        tmp_path = f"{path}.tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
        os.replace(tmp_path, path)
    except Exception as e:
        print(f"[Usgromana] Error saving {path}: {e}")
        try:
            if os.path.exists(f"{path}.tmp"):
                os.remove(f"{path}.tmp")
        except OSError:
            pass