import html
import json
import streamlit as st

from utils.styles import apply_styles, hero, card, pills
from utils.io import (
    load_messages,
    load_annotations,
    load_taxonomy,
    save_annotation,
    utc_now_iso,
)

st.set_page_config(page_title="Annotate", page_icon="📝", layout="wide")
apply_styles()

hero(
    "Annotate",
    "Label each first-user message using DSM-5 psychosocial/contextual categories.",
)

messages = load_messages()
annotations = load_annotations()
taxonomy = load_taxonomy()
label_lookup = {x["id"]: x["label"] for x in taxonomy}


def format_definition(text):
    lines = str(text).splitlines()
    html_parts = []

    for line in lines:
        line = html.escape(line.strip())

        if not line:
            continue

        is_code_line = line.startswith(("V", "995", "278"))
        is_numbered = line.startswith(("1.", "2.", "3.", "4.", "5."))
        is_heading = (
            not is_code_line
            and not is_numbered
            and len(line) < 90
            and line[0].isupper()
            and not line.endswith(".")
        )

        if is_heading:
            html_parts.append(
                f'<h4 style="margin-top:1rem; margin-bottom:0.4rem; font-weight:700;">{line}</h4>'
            )
        elif is_code_line:
            html_parts.append(
                f'<p style="margin-top:0.7rem; margin-bottom:0.35rem; font-weight:700;">{line}</p>'
            )
        elif is_numbered:
            html_parts.append(
                f'<p style="margin-left:1rem; margin-bottom:0.35rem; line-height:1.55;"><b>{line[:2]}</b> {line[2:].strip()}</p>'
            )
        else:
            html_parts.append(
                f'<p style="margin-bottom:0.55rem; line-height:1.6;">{line}</p>'
            )

    return (
        '<div style="max-height:520px; overflow-y:auto; padding-right:0.6rem; font-size:0.95rem;">'
        + "".join(html_parts)
        + "</div>"
    )


ADMIN_PASSWORD = st.secrets.get("ADMIN_PASSWORD", "admin123")

ALLOWED_EXPERT_IDS = {
    "u6045151",
    "u1655162",
    "1",
    "2",
    "3"
}

ANNOTATIONS_REQUIRED_PER_MESSAGE = 3
ANNOTATOR_IDS = sorted(list(ALLOWED_EXPERT_IDS))


def get_assigned_annotators(message_index):
    start = message_index % len(ANNOTATOR_IDS)

    
    return [
        ANNOTATOR_IDS[(start + offset) % len(ANNOTATOR_IDS)]
        for offset in range(ANNOTATIONS_REQUIRED_PER_MESSAGE)
    ]


messages = messages.copy()
messages["message_id"] = messages["message_id"].astype(str)
messages = messages.reset_index(drop=True)

assignment_lookup = {}

for idx, row in messages.iterrows():
    message_id = str(row["message_id"])
    assignment_lookup[message_id] = get_assigned_annotators(idx)

# -----------------------------------
# DEBUG: check assignment balance
# -----------------------------------

assignment_counts = {a: 0 for a in ANNOTATOR_IDS}

for annotators in assignment_lookup.values():
    for a in annotators:
        assignment_counts[a] += 1

print("Assignment counts:")
print(assignment_counts)

with st.sidebar:
    st.header("Annotator")

    annotator_id = st.text_input(
        "Expert ID",
        placeholder="expert_01",
    )



if not annotator_id:
    st.warning("Enter an Expert ID in the sidebar to begin.")
    st.stop()

annotator_id = annotator_id.strip()

if annotator_id not in ALLOWED_EXPERT_IDS:
    st.error("Invalid Expert ID. Please check your assigned Expert ID and try again.")
    st.stop()

assigned_message_ids = {
    message_id
    for message_id, assigned_annotators in assignment_lookup.items()
    if annotator_id in assigned_annotators
}

if not annotations.empty:
    annotations = annotations.copy()
    annotations["message_id"] = annotations["message_id"].astype(str)
    annotations["annotator_id"] = annotations["annotator_id"].astype(str)

    annotated_by_user = set(
        annotations.loc[
            annotations["annotator_id"] == str(annotator_id),
            "message_id",
        ]
    )
else:
    annotated_by_user = set()

completed_count = len(assigned_message_ids.intersection(annotated_by_user))
assigned_count = len(assigned_message_ids)
remaining_count = max(assigned_count - completed_count, 0)

with st.sidebar:
    st.metric("Completed", completed_count)
    st.metric("Remaining", remaining_count)
    st.metric("Assigned total", assigned_count)

    st.divider()

    st.header("Admin View")

    admin_password = st.text_input(
        "Admin Password",
        type="password",
    )

    is_admin = admin_password == ADMIN_PASSWORD

pool = messages[
    messages["message_id"].isin(assigned_message_ids)
    & ~messages["message_id"].isin(annotated_by_user)
].copy()

if pool.empty:
    st.success("You have completed all assigned messages.")
    st.stop()

pool_ids = pool["message_id"].astype(str).tolist()

if (
    "current_message_id" not in st.session_state
    or st.session_state.current_message_id is None
    or st.session_state.current_message_id not in pool_ids
):
    st.session_state.current_message_id = str(pool_ids[0])

current = pool[
    pool["message_id"].astype(str) == st.session_state.current_message_id
].iloc[0]

left, right = st.columns([2.15, 1])

with left:
    safe_msg = html.escape(str(current["first_user_message"]))
    card(f"<h3>First User Message</h3><p>{safe_msg}</p>", "user-card")

    st.subheader("DSM-5 categories")
    st.caption("Answer Yes / No / Maybe for every category before moving next.")

    category_decisions = {}
    selected_labels = []

    for item in taxonomy:
        st.markdown(f"### **{item['label']}**")

        decision = st.radio(
            "Decision",
            ["Yes", "No", "Maybe"],
            index=None,
            horizontal=True,
            key=f"{current['message_id']}_{item['id']}_decision",
            label_visibility="collapsed",
        )

        category_decisions[item["id"]] = decision

        if decision == "Yes":
            selected_labels.append(item["id"])

        with st.expander("Definition", expanded=False):
            st.markdown(
                format_definition(item["definition"]),
                unsafe_allow_html=True,
            )

    notes = st.text_area(
        "Notes / rationale",
        placeholder="Optional note about why you selected these labels",
    )

    next_clicked = st.button("Next", type="primary", use_container_width=True)

    if next_clicked:
        incomplete = [k for k, v in category_decisions.items() if v is None]

        if incomplete:
            st.error("Please answer Yes, No, or Maybe for every category before continuing.")

        elif "OUT_OF_SCOPE" in selected_labels and len(selected_labels) > 1:
            st.error("OUT_OF_SCOPE should not be marked Yes with any in-scope category.")

        elif not selected_labels and all(v != "Maybe" for v in category_decisions.values()):
            st.error("Please mark at least one category as Yes or Maybe.")

        else:
            row = {
                "message_id": str(current.get("message_id", "")),
                "conversation_id": str(current.get("conversation_id", "")),
                "first_user_message": str(current.get("first_user_message", "")),
                "annotator_id": str(annotator_id),
                "labels": ";".join(selected_labels),
                "category_decisions": json.dumps(category_decisions),
                "notes": notes,
                "timestamp": utc_now_iso(),
            }

            save_annotation(row)
            st.cache_data.clear()

            remaining_ids = [
                x for x in pool_ids if x != str(current["message_id"])
            ]

            if remaining_ids:
                st.session_state.current_message_id = remaining_ids[0]
            else:
                st.session_state.current_message_id = None

            st.rerun()

with right:
    if selected_labels:
        readable = [label_lookup.get(x, x) for x in selected_labels]
        st.markdown("**Selected Yes labels**", unsafe_allow_html=True)
        st.markdown(pills(readable), unsafe_allow_html=True)

    prior = annotations[
        annotations["message_id"].astype(str) == str(current["message_id"])
    ] if not annotations.empty else annotations

    if is_admin:
        st.subheader("Admin metadata")

        meta_rows = []

        for col in current.index:
            if col != "first_user_message":
                meta_rows.append(
                    f"<p><b>{html.escape(str(col))}:</b> "
                    f"{html.escape(str(current[col]))}</p>"
                )

        assigned_for_current = assignment_lookup.get(
            str(current["message_id"]),
            [],
        )

        meta_rows.append(
            f"<p><b>Assigned annotators:</b> {html.escape(', '.join(assigned_for_current))}</p>"
        )

        card("<h3>Message Metadata</h3>" + "".join(meta_rows), "info-card")

        st.divider()

        st.subheader("Other annotators")

        if prior.empty:
            st.info("No prior annotations for this message yet.")
        else:
            visible_cols = [
                col
                for col in [
                    "annotator_id",
                    "labels",
                    "category_decisions",
                    "notes",
                    "timestamp",
                ]
                if col in prior.columns
            ]

            st.dataframe(
                prior[visible_cols],
                use_container_width=True,
                hide_index=True,
            )
    else:
        st.info("Enter admin password to view metadata and prior annotations.")