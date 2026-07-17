from pathlib import Path
from datetime import datetime, timezone
import json
from typing import Any

import pandas as pd
import streamlit as st
from pymongo import ASCENDING, MongoClient
from pymongo.errors import DuplicateKeyError, PyMongoError

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
TAXONOMY_PATH = ROOT / "taxonomy" / "dsm_categories.json"
INPUT_PATH = DATA_DIR / "annotation_dataset_108.csv"
FINAL_LABELS_PATH = DATA_DIR / "final_labels.csv"

ANNOTATION_COLUMNS = [
    "message_id",
    "conversation_id",
    "first_user_message",
    "annotator_id",
    "study_phase",
    "batch_id",
    "original_annotator_id",
    "is_reassigned",
    "reassignment_id",
    "labels",
    "category_decisions",
    "notes",
    "timestamp",
]


@st.cache_resource
def get_mongodb_client() -> MongoClient:
    uri = str(st.secrets.get("MONGODB_URI", "")).strip()
    if not uri:
        raise RuntimeError("Missing MONGODB_URI in Streamlit secrets.")

    client = MongoClient(
        uri,
        serverSelectionTimeoutMS=10000,
        connectTimeoutMS=10000,
        socketTimeoutMS=10000,
        retryWrites=True,
    )
    client.admin.command("ping")
    return client


@st.cache_resource
def get_database():
    name = str(
        st.secrets.get("MONGODB_DATABASE", "annotation_study")
    ).strip() or "annotation_study"
    return get_mongodb_client()[name]


@st.cache_resource
def get_annotations_collection():
    collection = get_database()["annotations"]
    collection.create_index(
        [("message_id", ASCENDING), ("annotator_id", ASCENDING)],
        unique=True,
        name="unique_message_annotator",
    )
    return collection


@st.cache_resource
def get_acknowledgements_collection():
    collection = get_database()["acknowledgements"]
    collection.create_index(
        [("annotator_id", ASCENDING)],
        unique=True,
        name="unique_acknowledgement_annotator",
    )
    return collection


def _parse_category_decisions(value: Any) -> dict:
    if isinstance(value, dict):
        return value
    if not value:
        return {}
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def load_taxonomy() -> list[dict]:
    with TAXONOMY_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


@st.cache_data
def load_messages(path: Path = INPUT_PATH) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(
            columns=["message_id", "conversation_id", "first_user_message"]
        )

    df = pd.read_csv(path).fillna("")
    required = {"message_id", "first_user_message"}
    missing = required - set(df.columns)

    if missing:
        raise ValueError(
            f"Input file is missing required columns: {sorted(missing)}"
        )

    if "conversation_id" not in df.columns:
        df["conversation_id"] = ""

    df["message_id"] = df["message_id"].astype(str)
    return df


def load_annotations() -> pd.DataFrame:
    try:
        documents = list(
            get_annotations_collection().find(
                {},
                {"_id": 0, "created_at": 0},
            )
        )
    except PyMongoError as exc:
        raise RuntimeError(
            f"Could not load annotations from MongoDB: {exc}"
        ) from exc

    if not documents:
        return pd.DataFrame(columns=ANNOTATION_COLUMNS)

    rows = []
    for document in documents:
        row = {}
        for column in ANNOTATION_COLUMNS:
            value = document.get(column, "")
            if column == "category_decisions" and isinstance(value, dict):
                value = json.dumps(value, ensure_ascii=False)
            row[column] = value
        rows.append(row)

    df = pd.DataFrame(rows, columns=ANNOTATION_COLUMNS).fillna("")
    df["message_id"] = df["message_id"].astype(str)
    df["annotator_id"] = df["annotator_id"].astype(str)
    return df


def save_annotation(row: dict) -> None:
    document = {
        "message_id": str(row.get("message_id", "")).strip(),
        "conversation_id": str(row.get("conversation_id", "")),
        "first_user_message": str(row.get("first_user_message", "")),
        "annotator_id": str(row.get("annotator_id", "")).strip(),
        "study_phase": str(row.get("study_phase", "")).strip(),
        "batch_id": int(row.get("batch_id", 0) or 0),
        "original_annotator_id": str(
            row.get("original_annotator_id", "")
        ).strip(),
        "is_reassigned": bool(row.get("is_reassigned", False)),
        "reassignment_id": str(row.get("reassignment_id", "")).strip(),
        "labels": str(row.get("labels", "")),
        "category_decisions": _parse_category_decisions(
            row.get("category_decisions", {})
        ),
        "notes": str(row.get("notes", "")),
        "timestamp": str(row.get("timestamp") or utc_now_iso()),
        "created_at": datetime.now(timezone.utc),
    }

    if not document["message_id"] or not document["annotator_id"]:
        raise ValueError("message_id and annotator_id are required.")

    try:
        get_annotations_collection().insert_one(document)
    except DuplicateKeyError as exc:
        raise ValueError(
            "This message has already been annotated by this annotator."
        ) from exc
    except PyMongoError as exc:
        raise RuntimeError(
            f"Could not save annotation to MongoDB: {exc}"
        ) from exc


def load_acknowledgements() -> set[str]:
    try:
        documents = get_acknowledgements_collection().find(
            {},
            {"_id": 0, "annotator_id": 1},
        )
        return {
            str(document.get("annotator_id", "")).strip()
            for document in documents
            if str(document.get("annotator_id", "")).strip()
        }
    except PyMongoError as exc:
        raise RuntimeError(
            f"Could not load acknowledgements from MongoDB: {exc}"
        ) from exc


def save_acknowledgement(row: dict) -> None:
    annotator_id = str(row.get("annotator_id", "")).strip()
    if not annotator_id:
        raise ValueError("annotator_id is required.")

    document = {
        "annotator_id": annotator_id,
        "timestamp": str(row.get("timestamp") or utc_now_iso()),
        "created_at": datetime.now(timezone.utc),
    }

    try:
        get_acknowledgements_collection().update_one(
            {"annotator_id": annotator_id},
            {"$setOnInsert": document},
            upsert=True,
        )
    except PyMongoError as exc:
        raise RuntimeError(
            f"Could not save acknowledgement to MongoDB: {exc}"
        ) from exc


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")