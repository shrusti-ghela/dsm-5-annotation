import html
import streamlit as st
import pandas as pd
from utils.styles import apply_styles, hero, card, pills
from utils.io import load_annotations, FINAL_LABELS_PATH, utc_now_iso
from utils.agreement import disagreement_rows, split_labels

ADMIN_PASSWORD = st.secrets.get("ADMIN_PASSWORD", "admin123")

with st.sidebar:
    password = st.text_input("Admin password", type="password")

if password != ADMIN_PASSWORD:
    st.warning("This page is restricted to admin users.")
    st.stop()
    
st.set_page_config(page_title="Review Disagreements", page_icon="⚖️", layout="wide")
apply_styles()
hero("Review Disagreements", "Inspect messages where multiple annotators selected different label sets and optionally save adjudicated final labels.")

annotations = load_annotations()

if annotations.empty:
    st.info("No annotations yet.")
    st.stop()

disagree = disagreement_rows(annotations)
if disagree.empty:
    st.success("No disagreements found among messages with multiple annotators.")
    st.stop()

message_ids = disagree["message_id"].drop_duplicates().astype(str).tolist()
selected_mid = st.selectbox("Message with disagreement", message_ids)
rows = disagree[disagree["message_id"].astype(str) == selected_mid]
first_msg = rows.iloc[0]["first_user_message"]

card(f"<h3>First User Message</h3><p>{html.escape(str(first_msg))}</p>", "user-card")

st.subheader("Annotator labels")
st.dataframe(
    rows[["annotator_id", "labels", "confidence", "unclear", "notes", "timestamp", "taxonomy_version"]],
    use_container_width=True,
    hide_index=True,
)

all_labels = sorted(set().union(*rows["labels"].apply(split_labels).tolist()))
st.markdown("**All labels selected by at least one annotator**")
st.markdown(pills(all_labels), unsafe_allow_html=True)

st.divider()
st.subheader("Adjudicate final label")
final_labels = st.multiselect("Final labels", options=all_labels, default=all_labels)
adjudicator_id = st.text_input("Adjudicator ID", placeholder="adjudicator_01")
adjudication_notes = st.text_area("Adjudication notes")

if st.button("Save final adjudicated label", type="primary"):
    if not adjudicator_id:
        st.error("Enter an adjudicator ID.")
    elif not final_labels:
        st.error("Select at least one final label.")
    else:
        row = pd.DataFrame([
            {
                "message_id": selected_mid,
                "first_user_message": first_msg,
                "final_labels": ";".join(final_labels),
                "adjudicator_id": adjudicator_id,
                "adjudication_notes": adjudication_notes,
                "timestamp": utc_now_iso(),
            }
        ])
        if FINAL_LABELS_PATH.exists():
            old = pd.read_csv(FINAL_LABELS_PATH).fillna("")
            out = pd.concat([old, row], ignore_index=True)
        else:
            out = row
        out.to_csv(FINAL_LABELS_PATH, index=False)
        st.success("Final label saved.")
