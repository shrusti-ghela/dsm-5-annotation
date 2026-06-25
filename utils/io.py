from pathlib import Path
from datetime import datetime, timezone
import json
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
TAXONOMY_PATH = ROOT / "taxonomy" / "dsm_categories.json"
INPUT_PATH = DATA_DIR / "input_messages_v2.csv"
ANNOTATION_PATH = DATA_DIR / "annotations_v2.csv"
FINAL_LABELS_PATH = DATA_DIR / "final_labels.csv"
ACK_PATH = DATA_DIR / "acknowledgements.jsonl"

ANNOTATION_COLUMNS = [
    "message_id",
    "conversation_id",
    "first_user_message",
    "annotator_id",
    "labels",
    "confidence",
    "unclear",
    "notes",
    "timestamp",
    "taxonomy_version",
]

def load_acknowledgements():
    if not ACK_PATH.exists():
        return set()

    acknowledged = set()

    with ACK_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                row = json.loads(line)
                acknowledged.add(str(row.get("annotator_id", "")).strip())

    return acknowledged


def save_acknowledgement(row):
    ACK_PATH.parent.mkdir(parents=True, exist_ok=True)

    with ACK_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
        
def load_taxonomy() -> list[dict]:
    with open(TAXONOMY_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_messages(path: Path = INPUT_PATH) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=["message_id", "conversation_id", "first_user_message"])
    df = pd.read_csv(path).fillna("")
    required = {"message_id", "first_user_message"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Input file is missing required columns: {sorted(missing)}")
    if "conversation_id" not in df.columns:
        df["conversation_id"] = ""
    df["message_id"] = df["message_id"].astype(str)
    return df


def load_annotations() -> pd.DataFrame:
    if not ANNOTATION_PATH.exists():
        return pd.DataFrame(columns=ANNOTATION_COLUMNS)
    df = pd.read_csv(ANNOTATION_PATH).fillna("")
    for col in ANNOTATION_COLUMNS:
        if col not in df.columns:
            df[col] = ""
    df["message_id"] = df["message_id"].astype(str)
    return df[ANNOTATION_COLUMNS]


def save_annotation(row: dict) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    old = load_annotations()
    new = pd.DataFrame([row], columns=ANNOTATION_COLUMNS)
    out = pd.concat([old, new], ignore_index=True)
    out.to_csv(ANNOTATION_PATH, index=False)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
