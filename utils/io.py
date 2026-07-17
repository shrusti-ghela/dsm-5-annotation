from pathlib import Path
from datetime import datetime, timezone
import json
from typing import Any

import pandas as pd
import streamlit as st
from pymongo import ASCENDING, MongoClient
from pymongo.errors import PyMongoError


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
    "maybe_labels",
    "category_decisions",
    "notes",
    "timestamp",
]


@st.cache_resource
def get_mongodb_client() -> MongoClient:
    uri = str(st.secrets.get("MONGODB_URI", "")).strip()

    if not uri:
        raise RuntimeError(
            "Missing MONGODB_URI in Streamlit secrets."
        )

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
    database_name = str(
        st.secrets.get(
            "MONGODB_DATABASE",
            "annotation_study",
        )
    ).strip()

    if not database_name:
        database_name = "annotation_study"

    return get_mongodb_client()[database_name]


@st.cache_resource
def get_annotations_collection():
    collection = get_database()["annotations"]

    collection.create_index(
        [
            ("message_id", ASCENDING),
            ("annotator_id", ASCENDING),
        ],
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


@st.cache_resource
def get_batch_submissions_collection():
    collection = get_database()["batch_submissions"]

    collection.create_index(
        [
            ("annotator_id", ASCENDING),
            ("study_phase", ASCENDING),
            ("batch_id", ASCENDING),
        ],
        unique=True,
        name="unique_batch_submission",
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
    with TAXONOMY_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)


@st.cache_data
def load_messages(path: Path = INPUT_PATH) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(
            columns=[
                "message_id",
                "conversation_id",
                "first_user_message",
            ]
        )

    dataframe = pd.read_csv(path).fillna("")

    required_columns = {
        "message_id",
        "first_user_message",
    }

    missing_columns = required_columns - set(dataframe.columns)

    if missing_columns:
        raise ValueError(
            "Input file is missing required columns: "
            f"{sorted(missing_columns)}"
        )

    if "conversation_id" not in dataframe.columns:
        dataframe["conversation_id"] = ""

    dataframe["message_id"] = (
        dataframe["message_id"].astype(str)
    )

    return dataframe


def load_annotations() -> pd.DataFrame:
    try:
        documents = list(
            get_annotations_collection().find(
                {},
                {
                    "_id": 0,
                    "created_at": 0,
                    "updated_at": 0,
                },
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

            if (
                column == "category_decisions"
                and isinstance(value, dict)
            ):
                value = json.dumps(
                    value,
                    ensure_ascii=False,
                )

            row[column] = value

        rows.append(row)

    dataframe = pd.DataFrame(
        rows,
        columns=ANNOTATION_COLUMNS,
    ).fillna("")

    dataframe["message_id"] = (
        dataframe["message_id"].astype(str)
    )

    dataframe["annotator_id"] = (
        dataframe["annotator_id"].astype(str)
    )

    return dataframe


def get_annotation(
    annotator_id: str,
    message_id: str,
) -> dict | None:
    annotator_id = str(annotator_id).strip()
    message_id = str(message_id).strip()

    if not annotator_id or not message_id:
        return None

    try:
        document = get_annotations_collection().find_one(
            {
                "annotator_id": annotator_id,
                "message_id": message_id,
            },
            {
                "_id": 0,
                "created_at": 0,
                "updated_at": 0,
            },
        )

        return document

    except PyMongoError as exc:
        raise RuntimeError(
            "Could not retrieve the annotation from MongoDB: "
            f"{exc}"
        ) from exc


def is_batch_submitted(
    annotator_id: str,
    study_phase: str,
    batch_id: int,
) -> bool:
    annotator_id = str(annotator_id).strip()
    study_phase = str(study_phase).strip()
    batch_id = int(batch_id or 0)

    if not annotator_id:
        return False

    try:
        submission = (
            get_batch_submissions_collection().find_one(
                {
                    "annotator_id": annotator_id,
                    "study_phase": study_phase,
                    "batch_id": batch_id,
                },
                {"_id": 1},
            )
        )

        return submission is not None

    except PyMongoError as exc:
        raise RuntimeError(
            "Could not check the batch submission status: "
            f"{exc}"
        ) from exc


def submit_batch(
    annotator_id: str,
    study_phase: str,
    batch_id: int,
) -> None:
    annotator_id = str(annotator_id).strip()
    study_phase = str(study_phase).strip()
    batch_id = int(batch_id or 0)

    if not annotator_id:
        raise ValueError("annotator_id is required.")

    submitted_at = datetime.now(timezone.utc)

    try:
        get_batch_submissions_collection().update_one(
            {
                "annotator_id": annotator_id,
                "study_phase": study_phase,
                "batch_id": batch_id,
            },
            {
                "$setOnInsert": {
                    "annotator_id": annotator_id,
                    "study_phase": study_phase,
                    "batch_id": batch_id,
                    "submitted_at": submitted_at,
                }
            },
            upsert=True,
        )

    except PyMongoError as exc:
        raise RuntimeError(
            f"Could not submit the batch: {exc}"
        ) from exc


def save_annotation(row: dict) -> None:
    message_id = str(
        row.get("message_id", "")
    ).strip()

    annotator_id = str(
        row.get("annotator_id", "")
    ).strip()

    study_phase = str(
        row.get("study_phase", "")
    ).strip()

    batch_id = int(
        row.get("batch_id", 0) or 0
    )

    if not message_id or not annotator_id:
        raise ValueError(
            "message_id and annotator_id are required."
        )

    if is_batch_submitted(
        annotator_id=annotator_id,
        study_phase=study_phase,
        batch_id=batch_id,
    ):
        raise RuntimeError(
            "This batch has already been submitted and "
            "cannot be edited."
        )

    now = datetime.now(timezone.utc)

    document = {
        "message_id": message_id,
        "conversation_id": str(
            row.get("conversation_id", "")
        ),
        "first_user_message": str(
            row.get("first_user_message", "")
        ),
        "annotator_id": annotator_id,
        "study_phase": study_phase,
        "batch_id": batch_id,
        "original_annotator_id": str(
            row.get("original_annotator_id", "")
        ).strip(),
        "is_reassigned": bool(
            row.get("is_reassigned", False)
        ),
        "reassignment_id": str(
            row.get("reassignment_id", "")
        ).strip(),
        "labels": str(
            row.get("labels", "")
        ),
        "maybe_labels": str(
            row.get("maybe_labels", "")
        ),
        "category_decisions": _parse_category_decisions(
            row.get("category_decisions", {})
        ),
        "notes": str(
            row.get("notes", "")
        ),
        "timestamp": str(
            row.get("timestamp") or utc_now_iso()
        ),
        "updated_at": now,
    }

    try:
        get_annotations_collection().update_one(
            {
                "message_id": message_id,
                "annotator_id": annotator_id,
            },
            {
                "$set": document,
                "$setOnInsert": {
                    "created_at": now,
                },
            },
            upsert=True,
        )

    except PyMongoError as exc:
        raise RuntimeError(
            f"Could not save annotation to MongoDB: {exc}"
        ) from exc


def load_acknowledgements() -> set[str]:
    try:
        documents = (
            get_acknowledgements_collection().find(
                {},
                {
                    "_id": 0,
                    "annotator_id": 1,
                },
            )
        )

        return {
            str(
                document.get("annotator_id", "")
            ).strip()
            for document in documents
            if str(
                document.get("annotator_id", "")
            ).strip()
        }

    except PyMongoError as exc:
        raise RuntimeError(
            "Could not load acknowledgements from "
            f"MongoDB: {exc}"
        ) from exc


def save_acknowledgement(row: dict) -> None:
    annotator_id = str(
        row.get("annotator_id", "")
    ).strip()

    if not annotator_id:
        raise ValueError(
            "annotator_id is required."
        )

    document = {
        "annotator_id": annotator_id,
        "timestamp": str(
            row.get("timestamp") or utc_now_iso()
        ),
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
            "Could not save acknowledgement to "
            f"MongoDB: {exc}"
        ) from exc


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(
        timespec="seconds"
    )