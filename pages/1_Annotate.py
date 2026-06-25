import html
import json
import streamlit as st

from utils.styles import apply_styles, hero, card
from utils.io import (
    load_messages,
    load_annotations,
    load_taxonomy,
    load_acknowledgements,
    save_annotation,
    utc_now_iso,
)

st.set_page_config(page_title="Annotate", page_icon="📝", layout="wide")
apply_styles()

hero(
    "Annotate",
    "Identify the contextual conditions reflected in each help-seeking request.",
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
    "3",
}

ANNOTATIONS_REQUIRED_PER_MESSAGE = 3
ANNOTATOR_IDS = sorted(list(ALLOWED_EXPERT_IDS))


def get_assigned_annotators(message_index):
    start = message_index % len(ANNOTATOR_IDS)

    return [
        ANNOTATOR_IDS[(start + offset) % len(ANNOTATOR_IDS)]
        for offset in range(ANNOTATIONS_REQUIRED_PER_MESSAGE)
    ]


def get_yes_maybe_decision(message_id, category_id):
    yes_key = f"{message_id}_{category_id}_yes"
    maybe_key = f"{message_id}_{category_id}_maybe"

    if yes_key not in st.session_state:
        st.session_state[yes_key] = False

    if maybe_key not in st.session_state:
        st.session_state[maybe_key] = False

    def yes_changed():
        if st.session_state[yes_key]:
            st.session_state[maybe_key] = False

    def maybe_changed():
        if st.session_state[maybe_key]:
            st.session_state[yes_key] = False

    yes_col, maybe_col, _ = st.columns([1, 1, 8])

    with yes_col:
        st.checkbox(
            "Yes",
            key=yes_key,
            on_change=yes_changed,
        )

    with maybe_col:
        st.checkbox(
            "Maybe",
            key=maybe_key,
            on_change=maybe_changed,
        )

    if st.session_state[yes_key]:
        return "Yes"

    if st.session_state[maybe_key]:
        return "Maybe"

    return "No"


messages = messages.copy()
messages["message_id"] = messages["message_id"].astype(str)
messages = messages.drop_duplicates(subset=["message_id"]).reset_index(drop=True)

assignment_lookup = {}

for idx, row in messages.iterrows():
    message_id = str(row["message_id"])
    assignment_lookup[message_id] = get_assigned_annotators(idx)

if not annotations.empty:
    annotations = annotations.copy()
    annotations["message_id"] = annotations["message_id"].astype(str)
    annotations["annotator_id"] = annotations["annotator_id"].astype(str)


annotator_id = None
is_admin = False

with st.sidebar:
    st.header("Mode")

    mode = st.radio(
        "Choose mode",
        ["Annotation", "Review"],
        label_visibility="collapsed",
    )

    st.divider()

    if mode == "Annotation":
        st.header("Annotator")

        acknowledged_ids = load_acknowledgements()

        saved_annotator = st.session_state.get("verified_annotator", "").strip()

        if saved_annotator:
            annotator_id = saved_annotator

            if annotator_id not in ALLOWED_EXPERT_IDS:
                st.error("Invalid Expert ID. Please enter it again.")
                st.session_state.pop("verified_annotator", None)
                st.session_state.pop("instructions_acknowledged", None)
                st.stop()

            if annotator_id not in acknowledged_ids:
                st.warning(
                    "Please read and acknowledge the instructions before annotating."
                )
                st.page_link("app.py", label="Go to Instructions", icon="📘")
                st.stop()

            st.success(f"Expert ID: {annotator_id}")

        else:
            st.warning(
                "Enter your Expert ID to continue. All annotators must read the instructions first."
            )

            returning_id = st.text_input(
                "Expert ID / UNID",
                placeholder="e.g. u1234567",
            ).strip()

            left, center, right = st.columns([1, 2, 1])
            with center:
                if st.button("📘 Instructions", use_container_width=True):
                    st.switch_page("app.py")

            if returning_id:
                if returning_id not in ALLOWED_EXPERT_IDS:
                    st.error("Invalid Expert ID. Please check your assigned Expert ID.")
                    st.stop()

                if returning_id not in acknowledged_ids:
                    st.error(
                        "This Expert ID has not acknowledged the instructions yet. "
                        "Please read the instructions first."
                    )
                    st.stop()

                st.session_state["verified_annotator"] = returning_id
                st.session_state["instructions_acknowledged"] = True
                st.rerun()

            st.stop()

    else:
        st.header("Review")
        admin_password = st.text_input("Admin Password", type="password")
        is_admin = admin_password == ADMIN_PASSWORD
        annotator_id = ""


if mode == "Annotation":
    assigned_message_ids = {
        message_id
        for message_id, assigned_annotators in assignment_lookup.items()
        if annotator_id in assigned_annotators
    }

    annotated_by_user = (
        set(
            annotations.loc[
                annotations["annotator_id"] == str(annotator_id),
                "message_id",
            ]
        )
        if not annotations.empty
        else set()
    )

    completed_count = len(assigned_message_ids.intersection(annotated_by_user))
    assigned_count = len(assigned_message_ids)
    remaining_count = max(assigned_count - completed_count, 0)

    with st.sidebar:
        st.metric("Completed", completed_count)
        st.metric("Remaining", remaining_count)
        st.metric("Assigned total", assigned_count)

    pool = messages[
        messages["message_id"].isin(assigned_message_ids)
        & ~messages["message_id"].isin(annotated_by_user)
    ].copy()

    if pool.empty:
        st.success("You have completed all assigned messages.")
        st.stop()

else:
    if not is_admin:
        st.warning("Enter the admin password in the sidebar to review all samples.")
        st.stop()

    with st.sidebar:
        st.metric("Total samples", len(messages))
        st.metric("Total annotations", len(annotations))

    pool = messages.copy()

    st.info(
        "Admin review mode: you can view all samples, metadata, and prior annotations. "
        "Annotation controls are disabled."
    )


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

safe_msg = html.escape(str(current["first_user_message"]))
card(f"<h3>User Message</h3><p>{safe_msg}</p>", "user-card")


if mode == "Review":
    current_idx = pool_ids.index(str(current["message_id"]))

    prior = (
        annotations[
            annotations["message_id"].astype(str) == str(current["message_id"])
        ]
        if not annotations.empty
        else annotations
    )

    st.subheader("Annotations")

    if prior.empty:
        card("No prior annotations for this message yet.", "info-card")
    else:
        visible_cols = [
            col
            for col in [
                "message_id",
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

    nav1, nav2 = st.columns(2)

    if nav1.button("Previous", use_container_width=True):
        st.session_state.current_message_id = pool_ids[
            (current_idx - 1) % len(pool_ids)
        ]
        st.rerun()

    if nav2.button("Next", use_container_width=True):
        st.session_state.current_message_id = pool_ids[
            (current_idx + 1) % len(pool_ids)
        ]
        st.rerun()


else:
    st.subheader("Context Categories")
    st.caption(
        "Select Yes if the category clearly applies, Maybe if uncertain, or leave both unchecked if it does not apply."
    )

    category_decisions = {}
    selected_labels = []

    for item in taxonomy:
        st.markdown(f"### **{item['label']}**")

        decision = get_yes_maybe_decision(
            str(current["message_id"]),
            item["id"],
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
        if "OUT_OF_SCOPE" in selected_labels and len(selected_labels) > 1:
            st.error("OUT_OF_SCOPE should not be marked Yes with any in-scope category.")

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