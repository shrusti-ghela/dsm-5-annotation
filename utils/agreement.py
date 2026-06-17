import pandas as pd
from sklearn.metrics import cohen_kappa_score


def split_labels(value: str) -> set[str]:
    if not isinstance(value, str) or not value.strip():
        return set()
    return {x.strip() for x in value.split(";") if x.strip()}


def label_distribution(annotations: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for labels in annotations.get("labels", []):
        for label in split_labels(labels):
            rows.append(label)
    if not rows:
        return pd.DataFrame(columns=["label", "count"])
    return pd.Series(rows).value_counts().rename_axis("label").reset_index(name="count")


def pairwise_exact_agreement(annotations: pd.DataFrame) -> pd.DataFrame:
    if annotations.empty:
        return pd.DataFrame(columns=["message_id", "n_annotators", "n_unique_label_sets", "agreement"])
    df = annotations.copy()
    df["label_set"] = df["labels"].apply(lambda x: ";".join(sorted(split_labels(x))))
    grouped = df.groupby("message_id").agg(
        n_annotators=("annotator_id", "nunique"),
        n_unique_label_sets=("label_set", "nunique"),
    ).reset_index()
    grouped["agreement"] = grouped["n_unique_label_sets"].eq(1)
    return grouped


def disagreement_rows(annotations: pd.DataFrame) -> pd.DataFrame:
    exact = pairwise_exact_agreement(annotations)
    disagree_ids = exact.loc[(exact["n_annotators"] > 1) & (~exact["agreement"]), "message_id"]
    return annotations[annotations["message_id"].isin(disagree_ids)].sort_values(["message_id", "annotator_id"])


def binary_kappa_by_label(annotations: pd.DataFrame) -> pd.DataFrame:
    annotators = sorted(annotations["annotator_id"].dropna().unique())
    if len(annotators) != 2:
        return pd.DataFrame(columns=["label", "cohen_kappa", "note"])

    a1, a2 = annotators
    labels = sorted(set().union(*annotations["labels"].apply(split_labels).tolist())) if not annotations.empty else []
    message_ids = sorted(set(annotations.loc[annotations["annotator_id"] == a1, "message_id"]) & set(annotations.loc[annotations["annotator_id"] == a2, "message_id"]))

    rows = []
    for label in labels:
        y1, y2 = [], []
        for mid in message_ids:
            l1 = split_labels(annotations[(annotations["message_id"] == mid) & (annotations["annotator_id"] == a1)].iloc[-1]["labels"])
            l2 = split_labels(annotations[(annotations["message_id"] == mid) & (annotations["annotator_id"] == a2)].iloc[-1]["labels"])
            y1.append(int(label in l1))
            y2.append(int(label in l2))
        if len(set(y1 + y2)) < 2:
            kappa = None
            note = "No variation for this label"
        else:
            kappa = cohen_kappa_score(y1, y2)
            note = ""
        rows.append({"label": label, "cohen_kappa": kappa, "note": note})
    return pd.DataFrame(rows)
