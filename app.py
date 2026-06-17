import streamlit as st
from utils.styles import apply_styles, hero
from utils.io import load_messages, load_annotations

st.set_page_config(
    page_title="DSM-5 Help-Seeking Annotation",
    page_icon="📝",
    layout="wide",
)

apply_styles()

messages = load_messages()
annotations = load_annotations()

hero(
    "DSM-5 V/Z Categories Annotation",
    "Human annotation app for labeling first-user messages using DSM-5 V/Z categories.",
)

c1, c2, c3 = st.columns(3)
c1.metric("Input messages", len(messages))
c2.metric("Saved annotations", len(annotations))
c3.metric(
    "Unique annotators",
    annotations["annotator_id"].nunique() if not annotations.empty else 0,
)

st.divider()

with st.container(border=True):
    st.subheader("Annotation task")
    st.markdown(
        """
You will review one **first-user message** at a time and assign one or more
DSM-5 V/Z categories.

The goal is to identify what kind of real-life help-seeking dilemma the user
is bringing to the model.
"""
    )

with st.container(border=True):
    st.subheader("What to label")
    st.markdown(
        """
- Read only the first-user message shown on the annotation page.
- Select all DSM-5 categories that apply.
- Use multiple labels when the message clearly spans more than one category.
- Use **OUT_OF_SCOPE** only when the message is not a personal help-seeking or life-dilemma message.
- Do not combine **OUT_OF_SCOPE** with any in-scope category.
"""
    )

with st.container(border=True):
    st.subheader("Annotation fields")
    st.markdown(
        """
- **Expert ID:** your assigned annotator ID / UNID.
- **DSM-5 categories:** one or more applicable labels.
- **Confidence:** 1 = very uncertain, 5 = very confident.
- **Unclear / needs adjudication:** mark this when the message is ambiguous or hard to classify.
- **Notes / rationale:** optional explanation for difficult or borderline cases.
"""
    )

with st.container(border=True):
    st.subheader("Category set")
    st.markdown(
        """
- Relational Problems
- Abuse / Neglect
- Educational / Occupational Problems
- Housing / Economic Problems
- Social Environment Problems
- Legal / Crime Problems
- Health Service Encounters
- Other Psychosocial / Environmental Problems
- Personal History
- General Life Help-Seeking
- Out of Scope
"""
    )

with st.container(border=True):
    st.subheader("Admin-only pages")
    st.markdown(
        """
The annotation page is available to annotators using their Expert ID.

The following pages are restricted to admins with a password:

- **Review Disagreements:** inspect conflicting annotations and adjudication cases.
- **Export Stats:** download annotations and inspect label distributions/agreement.
"""
    )

st.info("Use the sidebar navigation to start annotating.")