import streamlit as st
import pandas as pd
from utils.styles import apply_styles, hero
from utils.io import load_annotations, ANNOTATION_PATH, FINAL_LABELS_PATH
from utils.agreement import label_distribution, pairwise_exact_agreement, disagreement_rows, binary_kappa_by_label

ADMIN_PASSWORD = st.secrets.get("ADMIN_PASSWORD", "admin123")

with st.sidebar:
    password = st.text_input("Admin password", type="password")

if password != ADMIN_PASSWORD:
    st.warning("This page is restricted to admin users.")
    st.stop()
    
st.set_page_config(page_title="Export Stats", page_icon="📊", layout="wide")
apply_styles()
hero("Export & Stats", "Download annotations, inspect category distributions, and compute simple agreement diagnostics.")

annotations = load_annotations()

if annotations.empty:
    st.info("No annotations yet.")
    st.stop()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Annotations", len(annotations))
c2.metric("Unique messages", annotations["message_id"].nunique())
c3.metric("Annotators", annotations["annotator_id"].nunique())
c4.metric("Unclear flags", int(annotations["unclear"].astype(str).str.lower().isin(["true", "1", "yes"]).sum()))

st.subheader("Download")
with open(ANNOTATION_PATH, "rb") as f:
    st.download_button("Download annotations.csv", f, file_name="annotations.csv", mime="text/csv")

if FINAL_LABELS_PATH.exists():
    with open(FINAL_LABELS_PATH, "rb") as f:
        st.download_button("Download final_labels.csv", f, file_name="final_labels.csv", mime="text/csv")

st.divider()
st.subheader("Label distribution")
dist = label_distribution(annotations)
st.dataframe(dist, use_container_width=True, hide_index=True)
if not dist.empty:
    st.bar_chart(dist.set_index("label"))

st.divider()
st.subheader("Exact label-set agreement")
exact = pairwise_exact_agreement(annotations)
st.dataframe(exact, use_container_width=True, hide_index=True)
if not exact.empty:
    multi = exact[exact["n_annotators"] > 1]
    if not multi.empty:
        st.metric("Exact agreement among multi-annotated messages", f"{multi['agreement'].mean():.1%}")

st.divider()
st.subheader("Cohen's kappa by label")
st.caption("This is shown only when exactly two annotators are present. It treats each DSM category as a binary yes/no decision.")
kappa = binary_kappa_by_label(annotations)
st.dataframe(kappa, use_container_width=True, hide_index=True)

st.divider()
st.subheader("Disagreements")
disagree = disagreement_rows(annotations)
st.dataframe(disagree, use_container_width=True, hide_index=True)
