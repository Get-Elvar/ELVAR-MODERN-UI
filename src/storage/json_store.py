import json
import os


def load_json(path, default, logger=None):
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as exc:
        if logger:
            logger.exception("Failed to load JSON from %s: %s", path, exc)
    return default


def save_json(path, data, logger=None):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as exc:
        if logger:
            logger.exception("Failed to save JSON to %s: %s", path, exc)
        return False
