import html
import random
import streamlit as st
import pandas as pd
from utils.styles import apply_styles, hero, card, pills
from utils.io import load_messages, load_annotations, load_taxonomy, save_annotation, utc_now_iso

st.set_page_config(page_title="Annotate", page_icon="📝", layout="wide")
apply_styles()
hero("Annotate", "Label each first-user message using DSM-5 psychosocial/contextual categories.")

messages = load_messages()
annotations = load_annotations()
taxonomy = load_taxonomy()
label_lookup = {x["id"]: x["label"] for x in taxonomy}

ADMIN_PASSWORD = st.secrets.get("ADMIN_PASSWORD", "admin123")

ALLOWED_EXPERT_IDS = {
    "u6045151",
    "u1655162",
    "1", 
    "2"
}


with st.sidebar:
    st.header("Annotator")
    annotator_id = st.text_input("Expert ID", placeholder="expert_01")
    taxonomy_version = st.text_input("Taxonomy version", value="v1")

    st.divider()
    st.header("Admin")
    admin_password = st.text_input("Admin password", type="password")
    is_admin = admin_password == ADMIN_PASSWORD

    st.divider()
    st.header("Sampling")
    order = st.radio("Message order", ["Sequential", "Random"], horizontal=False)
    include_previously_done = st.checkbox("Show messages I already annotated", value=False)
    st.divider()

if not annotator_id:
    st.warning("Enter an Expert ID in the sidebar to begin.")
    st.stop()

annotator_id = annotator_id.strip()

if annotator_id not in ALLOWED_EXPERT_IDS:
    st.error("Invalid Expert ID. Please check your assigned Expert ID and try again.")
    st.stop()

# Use unique message IDs, not raw rows, so duplicate saves do not break counts.
annotated_by_user = (
    set(
        annotations.loc[
            annotations["annotator_id"].astype(str) == str(annotator_id),
            "message_id",
        ].astype(str)
    )
    if not annotations.empty
    else set()
)

completed_count = len(annotated_by_user)
remaining_count = max(len(messages) - completed_count, 0)

if include_previously_done:
    pool = messages.copy()
else:
    pool = messages[
        ~messages["message_id"].astype(str).isin(annotated_by_user)
    ].copy()

with st.sidebar:
    st.metric("Total messages", len(messages))
    st.metric("Completed by you", completed_count)
    st.metric("Remaining for you", remaining_count)

if pool.empty:
    st.success("You have completed all available messages.")
    st.stop()

pool_ids = pool["message_id"].astype(str).tolist()

if (
    "current_message_id" not in st.session_state
    or st.session_state.current_message_id is None
    or st.session_state.current_message_id not in pool_ids
):
    st.session_state.current_message_id = (
        str(random.choice(pool_ids)) if order == "Random" else str(pool_ids[0])
    )

current = pool[
    pool["message_id"].astype(str) == st.session_state.current_message_id
].iloc[0]

left, right = st.columns([2.15, 1])

with left:
    safe_msg = html.escape(str(current["first_user_message"]))
    card(f"<h3>First User Message</h3><p>{safe_msg}</p>", "user-card")

    selected_labels = []
    st.subheader("DSM-5 categories")
    st.caption(
        "Multi-label is allowed. Use OUT_OF_SCOPE only when the message is not a help-seeking life dilemma."
    )

    for item in taxonomy:
        cols = st.columns([0.08, 0.92])

        with cols[0]:
            checked = st.checkbox(
                "",
                key=f"{current['message_id']}_{item['id']}",
                label_visibility="collapsed",
            )

        with cols[1]:
            st.markdown(f"**{item['label']}**")
            with st.expander("Definition"):
                st.code(item["definition"], language=None)

        if checked:
            selected_labels.append(item["id"])

    st.divider()

    confidence = st.slider(
        "Confidence",
        1,
        5,
        3,
        help="1 = very uncertain, 5 = very confident",
    )

    unclear = st.checkbox("Unclear / needs adjudication")

    notes = st.text_area(
        "Notes / rationale",
        placeholder="Optional note about why you selected these labels",
    )

    b1, b2, b3 = st.columns(3)
    save = b1.button("Save annotation", type="primary", use_container_width=True)
    skip = b2.button("Skip", use_container_width=True)
    choose_random = b3.button("Random message", use_container_width=True)

    if save:
        if not selected_labels:
            st.error("Please select at least one category.")
        elif "OUT_OF_SCOPE" in selected_labels and len(selected_labels) > 1:
            st.error("OUT_OF_SCOPE should not be combined with in-scope categories.")
        else:
            row = {
                "message_id": str(current.get("message_id", "")),
                "conversation_id": str(current.get("conversation_id", "")),
                "first_user_message": str(current.get("first_user_message", "")),
                "annotator_id": str(annotator_id),
                "labels": ";".join(selected_labels),
                "confidence": confidence,
                "unclear": bool(unclear),
                "notes": notes,
                "timestamp": utc_now_iso(),
                "taxonomy_version": taxonomy_version,
            }

            save_annotation(row)

            # Clear cached loaders so counts update immediately after saving.
            st.cache_data.clear()

            remaining_ids = [
                x for x in pool_ids if x != str(current["message_id"])
            ]

            if remaining_ids:
                st.session_state.current_message_id = (
                    random.choice(remaining_ids)
                    if order == "Random"
                    else remaining_ids[0]
                )
            else:
                st.session_state.current_message_id = None

            st.rerun()

    if skip:
        ids = pool["message_id"].astype(str).tolist()
        idx = ids.index(str(current["message_id"]))
        st.session_state.current_message_id = ids[(idx + 1) % len(ids)]
        st.rerun()

    if choose_random:
        st.session_state.current_message_id = str(random.choice(pool_ids))
        st.rerun()

with right:
    meta_rows = []

    for col in current.index:
        if col not in ["first_user_message"]:
            meta_rows.append(
                f"<p><b>{html.escape(str(col))}:</b> {html.escape(str(current[col]))}</p>"
            )

    card("<h3>Metadata</h3>" + "".join(meta_rows), "info-card")

    if selected_labels:
        readable = [label_lookup.get(x, x) for x in selected_labels]
        st.markdown("**Selected labels**", unsafe_allow_html=True)
        st.markdown(pills(readable), unsafe_allow_html=True)

    prior = annotations[
        annotations["message_id"].astype(str) == str(current["message_id"])
    ]

    if is_admin and not prior.empty:
        st.subheader("Prior annotations")
        st.dataframe(
            prior[
                [
                    "annotator_id",
                    "labels",
                    "confidence",
                    "unclear",
                    "notes",
                    "timestamp",
                ]
            ],
            use_container_width=True,
            hide_index=True,
        )