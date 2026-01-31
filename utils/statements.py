import random
from pathlib import Path

STATEMENTS_DIR = Path("statements")

WEAPON_TO_FILE = {
    "marketing": "marketing.txt",
    "analytics": "analytics.txt",
    "copywriting": "copywriting.txt",
    "design": "design.txt",
    "management": "management.txt",
    "video": "video.txt",
    "other": "other.txt",
}


def _parse_line(line: str):
    parts = [p.strip() for p in line.split("|")]
    if len(parts) < 4:
        return None
    try:
        level = int(parts[0])
    except ValueError:
        return None

    is_truth = parts[1].lower() == "true"
    statement = parts[2]
    wisdom_prompt = parts[3]
    return {"level": level, "is_truth": is_truth, "statement": statement, "wisdom_prompt": wisdom_prompt}


def load_statements(weapon: str):
    filename = WEAPON_TO_FILE.get(weapon, "other.txt")
    path = STATEMENTS_DIR / filename
    if not path.exists():
        path = STATEMENTS_DIR / "other.txt"

    rounds = {1: [], 2: [], 3: []}

    with path.open("r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            parsed = _parse_line(line)
            if not parsed:
                continue
            if parsed["level"] in (1, 2, 3):
                rounds[parsed["level"]].append(parsed)

    return rounds


def get_statement_for_round(weapon: str, round_num: int):
    rounds = load_statements(weapon)
    pool = rounds.get(round_num, [])
    if not pool:
        return {
            "statement": "Утверждения для этого раунда не найдены.",
            "is_truth": True,
            "wisdom_prompt": "Проверь, что statements/*.txt заполнены корректно.",
        }
    return random.choice(pool)
