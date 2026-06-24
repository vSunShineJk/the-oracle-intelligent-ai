from pathlib import Path

_DIR = Path(__file__).parent

def read_memory(filename: str) -> str:
    path = _DIR / filename
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")

def append_memory(filename: str, content: str) -> None:
    path = _DIR / filename
    with open(path, "a", encoding="utf-8") as f:
        f.write("\n" + content)