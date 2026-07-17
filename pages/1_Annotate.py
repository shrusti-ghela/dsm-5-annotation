import html
import json
import re

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
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

if st.session_state.pop("scroll_to_top", False):
    components.html(
        """
        <script>
        function forceScrollToTop() {
            const doc = window.parent.document;

            const targets = [
                doc.querySelector('[data-testid="stAppViewContainer"]'),
                doc.querySelector('[data-testid="stMain"]'),
                doc.querySelector('section.main'),
                doc.documentElement,
                doc.body
            ];

            targets.forEach((target) => {
                if (!target) return;

                try {
                    target.scrollTop = 0;
                } catch (error) {}

                try {
                    target.scrollTo({
                        top: 0,
                        left: 0,
                        behavior: "auto"
                    });
                } catch (error) {}
            });

            const mainBlock = doc.querySelector(
                '[data-testid="stMainBlockContainer"]'
            );

            if (mainBlock) {
                try {
                    mainBlock.scrollIntoView({
                        behavior: "auto",
                        block: "start"
                    });
                } catch (error) {}
            }

            try {
                window.parent.scrollTo(0, 0);
            } catch (error) {}
        }

        forceScrollToTop();
        [50, 100, 200, 400, 700, 1000].forEach((delay) => {
            setTimeout(forceScrollToTop, delay);
        });
        </script>
        """,
        height=0,
        width=0,
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

# -----------------------------------------------------------------------------
# STUDY / PARTICIPANT-BATCH CONFIGURATION
# -----------------------------------------------------------------------------
# Only these selected annotators receive formal main-study batches.
# Replace the placeholder entries with the final selected annotator uNIDs.
FORMAL_ANNOTATOR_IDS = [
    "u1509787",
    "u1276376",
    "u1588664",  
    "u1589107",  
]
FORMAL_ANNOTATOR_ID_SET = set(FORMAL_ANNOTATOR_IDS)

# Anyone with a correctly formatted University of Utah uNID can access the pilot.
UNID_PATTERN = re.compile(r"^u\d{7}$", re.IGNORECASE)


def normalize_unid(value: str) -> str | None:
    """Return a normalized uNID, or None when the value is invalid."""
    unid = str(value).strip().lower()

    if not UNID_PATTERN.fullmatch(unid):
        return None

    return unid

PILOT_SIZE = 8
MAIN_STUDY_SIZE = 100

# Each participant receives exactly 50 main-study prompts:
# one personal batch of 8 prompts and six personal batches of 7 prompts.
PARTICIPANT_BATCH_SIZES = [8] + [7] * 6
TOTAL_PARTICIPANT_BATCHES = len(PARTICIPANT_BATCH_SIZES)
assert sum(PARTICIPANT_BATCH_SIZES) == 50

# Pilot is always available.
# Release personal main-study batches by adding their numbers here.
# Examples:
#   set()             -> pilot only
#   {1}               -> pilot + personal batch 1
#   {1, 2, 3}         -> pilot + personal batches 1-3
#   set(range(1, 8))  -> pilot + all seven personal batches
RELEASED_PARTICIPANT_BATCHES = set()

# Optional reassignment rules. Leave this empty during the pilot unless needed.
# Each rule transfers only unfinished prompts from one participant batch.
# Candidate replacements are tried in order. A candidate is skipped when they
# are already assigned to, or have already annotated, that message.
#
# Example:
# REASSIGNMENT_RULES = [
#     {
#         "reassignment_id": "r1",
#         "from_annotator": "1",
#         "participant_batch_id": 3,
#         "to_annotators": ["2", "u6045151", "u1655162"],
#     }
# ]
REASSIGNMENT_RULES = []
# REASSIGNMENT_RULES = [
#     {
#         "reassignment_id": "r1",
#         "from_annotator": "u6045151",
#         "participant_batch_id": 1,
#         "to_annotators": [
#             "2",
#             "1",
#             "u1655162",
#         ],
#     }
# ]

def build_balanced_main_pairs():
    """Return 100 annotator pairs with exactly 50 assignments per annotator."""
    if len(FORMAL_ANNOTATOR_IDS) != 4:
        raise ValueError(
            "Exactly four formal annotator uNIDs are required before main-study "
            "assignments can be generated. Update FORMAL_ANNOTATOR_IDS."
        )

    a, b, c, d = FORMAL_ANNOTATOR_IDS

    all_six_pairs = [
        (a, b),
        (a, c),
        (a, d),
        (b, c),
        (b, d),
        (c, d),
    ]

    final_four_pairs = [
        (a, b),
        (c, d),
        (a, c),
        (b, d),
    ]

    pairs = all_six_pairs * 16 + final_four_pairs
    assert len(pairs) == MAIN_STUDY_SIZE

    counts = {annotator: 0 for annotator in FORMAL_ANNOTATOR_IDS}
    for pair in pairs:
        for annotator in pair:
            counts[annotator] += 1

    assert all(count == 50 for count in counts.values())
    return pairs


MAIN_ASSIGNMENT_PAIRS = build_balanced_main_pairs()


def assign_personal_batches(main_df, main_pairs):
    """
    Create annotator-specific batches.

    Each annotator receives exactly 50 assigned prompts, divided into seven
    personal batches sized [8, 7, 7, 7, 7, 7, 7]. Messages are balanced by
    character length separately for each annotator.
    """
    if len(main_df) != MAIN_STUDY_SIZE:
        raise ValueError(
            f"Expected {MAIN_STUDY_SIZE} main-study messages, "
            f"but received {len(main_df)}."
        )

    message_lengths = (
        main_df["first_user_message"]
        .fillna("")
        .astype(str)
        .str.len()
        .tolist()
    )

    assignments = []

    for annotator_id in FORMAL_ANNOTATOR_IDS:
        assigned_indices = [
            main_idx
            for main_idx, pair in enumerate(main_pairs)
            if annotator_id in pair
        ]

        if len(assigned_indices) != 50:
            raise ValueError(
                f"Annotator {annotator_id} has {len(assigned_indices)} main "
                "assignments instead of 50."
            )

        batch_total_lengths = [0] * TOTAL_PARTICIPANT_BATCHES
        batch_counts = [0] * TOTAL_PARTICIPANT_BATCHES
        batch_for_index = {}

        longest_first = sorted(
            assigned_indices,
            key=lambda idx: (-message_lengths[idx], idx),
        )

        for main_idx in longest_first:
            eligible_batches = [
                batch_idx
                for batch_idx, target_size in enumerate(PARTICIPANT_BATCH_SIZES)
                if batch_counts[batch_idx] < target_size
            ]

            selected_batch = min(
                eligible_batches,
                key=lambda batch_idx: (
                    batch_total_lengths[batch_idx],
                    batch_counts[batch_idx],
                    batch_idx,
                ),
            )

            batch_for_index[main_idx] = selected_batch + 1
            batch_counts[selected_batch] += 1
            batch_total_lengths[selected_batch] += message_lengths[main_idx]

        assert batch_counts == PARTICIPANT_BATCH_SIZES

        for main_idx in assigned_indices:
            assignments.append(
                {
                    "message_id": str(main_df.iloc[main_idx]["message_id"]),
                    "annotator_id": str(annotator_id),
                    "study_phase": "main",
                    "participant_batch_id": int(batch_for_index[main_idx]),
                    "is_released": (
                        batch_for_index[main_idx]
                        in RELEASED_PARTICIPANT_BATCHES
                    ),
                    "original_annotator_id": str(annotator_id),
                    "is_reassigned": False,
                    "reassignment_id": "",
                    "reassignment_batch_label": "",
                }
            )

    return assignments


def prepare_study(messages_df):
    """
    Prepare the 8-message pilot and 100-message main study.

    Expected row order:
      rows 0-7   = pilot
      rows 8-107 = main study

    Pilot assignments are added dynamically after a participant logs in.
    """
    expected = PILOT_SIZE + MAIN_STUDY_SIZE

    if len(messages_df) < expected:
        st.error(
            f"Expected at least {expected} unique messages "
            f"({PILOT_SIZE} pilot + {MAIN_STUDY_SIZE} main), "
            f"but load_messages() returned {len(messages_df)}."
        )
        st.stop()

    study_messages = messages_df.iloc[:expected].copy().reset_index(drop=True)
    study_messages["study_phase"] = "main"
    study_messages.loc[: PILOT_SIZE - 1, "study_phase"] = "pilot"

    main_df = study_messages.iloc[PILOT_SIZE:].copy().reset_index(drop=True)

    assignment_rows = assign_personal_batches(
        main_df,
        MAIN_ASSIGNMENT_PAIRS,
    )

    return study_messages, assignment_rows


def add_pilot_assignments(
    assignments_df: pd.DataFrame,
    messages_df: pd.DataFrame,
    annotator_id: str,
) -> pd.DataFrame:
    """
    Give every valid uNID access to all pilot messages.

    Formal main-study assignments remain limited to FORMAL_ANNOTATOR_IDS.
    """
    updated = assignments_df.copy()

    pilot_messages = messages_df[
        messages_df["study_phase"] == "pilot"
    ].copy()

    existing_pairs = set()

    if not updated.empty:
        existing_pairs = set(
            zip(
                updated["message_id"].astype(str),
                updated["annotator_id"].astype(str),
            )
        )

    new_rows = []

    for _, pilot_message in pilot_messages.iterrows():
        message_id = str(pilot_message["message_id"])
        pair = (message_id, str(annotator_id))

        if pair in existing_pairs:
            continue

        new_rows.append(
            {
                "message_id": message_id,
                "annotator_id": str(annotator_id),
                "study_phase": "pilot",
                "participant_batch_id": 0,
                "is_released": True,
                "original_annotator_id": str(annotator_id),
                "is_reassigned": False,
                "reassignment_id": "",
                "reassignment_batch_label": "",
            }
        )

    if new_rows:
        updated = pd.concat(
            [updated, pd.DataFrame(new_rows)],
            ignore_index=True,
        )

    return updated

def apply_reassignments(assignments_df, annotations_df):
    """Transfer only unfinished assignments while preventing duplicate annotation.

    A replacement is never assigned a message when they are already assigned to
    that message or already have a saved annotation for it. Completed work by the
    original annotator is never moved.
    """
    updated = assignments_df.copy()

    if not REASSIGNMENT_RULES:
        return updated

    completed_pairs = set()
    if not annotations_df.empty:
        completed_pairs = set(
            zip(
                annotations_df["message_id"].astype(str),
                annotations_df["annotator_id"].astype(str),
            )
        )

    for rule in REASSIGNMENT_RULES:
        reassignment_id = str(rule.get("reassignment_id", "")).strip()
        from_annotator = str(rule.get("from_annotator", "")).strip()
        participant_batch_id = int(rule.get("participant_batch_id", -1))
        candidates = [str(x).strip() for x in rule.get("to_annotators", [])]

        if not reassignment_id:
            raise ValueError("Every reassignment rule needs a reassignment_id.")
        if from_annotator not in FORMAL_ANNOTATOR_ID_SET:
            raise ValueError(f"Unknown original annotator: {from_annotator}")
        if participant_batch_id not in range(1, TOTAL_PARTICIPANT_BATCHES + 1):
            raise ValueError(
                f"Invalid participant_batch_id {participant_batch_id} "
                f"for reassignment {reassignment_id}."
            )
        if not candidates:
            raise ValueError(
                f"Reassignment {reassignment_id} needs at least one replacement candidate."
            )
        if any(candidate not in FORMAL_ANNOTATOR_ID_SET for candidate in candidates):
            raise ValueError(
                f"Reassignment {reassignment_id} contains an unknown replacement annotator."
            )
        if from_annotator in candidates:
            raise ValueError(
                f"Reassignment {reassignment_id} cannot assign work back to {from_annotator}."
            )

        source_mask = (
            (updated["annotator_id"].astype(str) == from_annotator)
            & (updated["study_phase"] == "main")
            & (updated["participant_batch_id"] == participant_batch_id)
            & (~updated["is_reassigned"].astype(bool))
        )
        source_indices = updated.index[source_mask].tolist()

        if not source_indices:
            raise ValueError(
                f"No original assignments found for annotator {from_annotator}, "
                f"batch {participant_batch_id}."
            )

        moved = 0
        for row_index in source_indices:
            message_id = str(updated.at[row_index, "message_id"])

            # Never move an assignment the original annotator already completed.
            if (message_id, from_annotator) in completed_pairs:
                continue

            currently_assigned = set(
                updated.loc[
                    updated["message_id"].astype(str) == message_id,
                    "annotator_id",
                ].astype(str)
            )
            already_completed = {
                annotator
                for completed_message, annotator in completed_pairs
                if completed_message == message_id
            }
            forbidden = currently_assigned | already_completed
            forbidden.discard(from_annotator)

            replacement = next(
                (candidate for candidate in candidates if candidate not in forbidden),
                None,
            )

            if replacement is None:
                raise ValueError(
                    f"Could not reassign message {message_id} from {from_annotator}. "
                    "Every configured replacement is already assigned to or has "
                    "already annotated this message."
                )

            updated.at[row_index, "original_annotator_id"] = from_annotator
            updated.at[row_index, "annotator_id"] = replacement
            updated.at[row_index, "is_reassigned"] = True
            updated.at[row_index, "reassignment_id"] = reassignment_id
            updated.at[row_index, "reassignment_batch_label"] = (
                f"Reassigned batch {reassignment_id}"
            )
            updated.at[row_index, "is_released"] = True
            moved += 1

        if moved == 0:
            # This is allowed when the original participant already finished the batch.
            continue

    # Final safety check: no participant can hold duplicate assignments for a message.
    duplicates = updated.duplicated(
        subset=["message_id", "annotator_id"],
        keep=False,
    )
    if duplicates.any():
        duplicate_rows = updated.loc[duplicates, ["message_id", "annotator_id"]]
        raise ValueError(
            "Reassignment produced duplicate message/annotator assignments: "
            f"{duplicate_rows.to_dict(orient='records')}"
        )

    return updated


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
messages, assignment_rows = prepare_study(messages)

assignments = pd.DataFrame(assignment_rows)

if not annotations.empty:
    annotations = annotations.copy()
    annotations["message_id"] = annotations["message_id"].astype(str)
    annotations["annotator_id"] = annotations["annotator_id"].astype(str)

assignments = apply_reassignments(assignments, annotations)


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
        st.header("Participant")

        acknowledged_ids = {
            str(value).strip().lower()
            for value in load_acknowledgements()
        }

        saved_annotator = normalize_unid(
            st.session_state.get("verified_annotator", "")
        )

        if saved_annotator:
            annotator_id = saved_annotator

            if annotator_id not in acknowledged_ids:
                st.warning(
                    "Please read and acknowledge the study information "
                    "and instructions before annotating."
                )
                st.page_link(
                    "app.py",
                    label="Go to Instructions",
                    icon="📘",
                )
                st.stop()

            st.session_state["verified_annotator"] = annotator_id
            st.success(f"uNID: {annotator_id}")

            if annotator_id in FORMAL_ANNOTATOR_ID_SET:
                st.caption(
                    "You have access to the pilot and your currently released "
                    "formal annotation batches."
                )
            else:
                st.caption(
                    "You currently have access to the pilot testing batch."
                )

        else:
            st.warning(
                "Enter your University of Utah uNID to continue. "
                "You must acknowledge the instructions first."
            )

            returning_id_input = st.text_input(
                "University of Utah uNID",
                placeholder="e.g. u1234567",
                max_chars=8,
            )

            returning_id = normalize_unid(returning_id_input)

            left, center, right = st.columns([1, 2, 1])

            with center:
                if st.button(
                    "📘 Instructions",
                    use_container_width=True,
                ):
                    st.switch_page("app.py")

            if returning_id_input and returning_id is None:
                st.error(
                    "Enter a valid uNID in the format u followed by "
                    "7 digits, such as u1234567."
                )
                st.stop()

            if returning_id:
                if returning_id not in acknowledged_ids:
                    st.error(
                        "This uNID has not acknowledged the study information "
                        "and instructions yet. Please complete the instructions "
                        "page first."
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
    assignments = add_pilot_assignments(
        assignments_df=assignments,
        messages_df=messages,
        annotator_id=str(annotator_id),
    )

    user_assignments = assignments[
        assignments["annotator_id"] == str(annotator_id)
    ].copy()

    released_user_assignments = user_assignments[
        user_assignments["is_released"]
    ].copy()

    annotated_by_user = (
        set(
            annotations.loc[
                annotations["annotator_id"] == str(annotator_id),
                "message_id",
            ].astype(str)
        )
        if not annotations.empty
        else set()
    )

    assigned_message_ids = set(
        released_user_assignments["message_id"].astype(str)
    )

    completed_count = len(
        assigned_message_ids.intersection(annotated_by_user)
    )
    assigned_count = len(assigned_message_ids)
    remaining_count = max(assigned_count - completed_count, 0)

    pilot_assignments = released_user_assignments[
        released_user_assignments["study_phase"] == "pilot"
    ]
    pilot_ids = set(pilot_assignments["message_id"].astype(str))
    pilot_completed = len(pilot_ids.intersection(annotated_by_user))

    released_main_assignments = released_user_assignments[
        released_user_assignments["study_phase"] == "main"
    ]
    released_main_ids = set(
        released_main_assignments["message_id"].astype(str)
    )
    main_completed = len(
        released_main_ids.intersection(annotated_by_user)
    )

    completed_main_batches = 0
    for batch_id in sorted(RELEASED_PARTICIPANT_BATCHES):
        batch_ids = set(
            released_main_assignments.loc[
                (released_main_assignments["participant_batch_id"] == batch_id)
                & (~released_main_assignments["is_reassigned"].astype(bool)),
                "message_id",
            ].astype(str)
        )
        if batch_ids and batch_ids.issubset(annotated_by_user):
            completed_main_batches += 1

    reassigned_for_user = released_user_assignments[
        released_user_assignments["is_reassigned"].astype(bool)
    ]
    reassignment_ids = sorted(
        reassigned_for_user["reassignment_id"].dropna().astype(str).unique()
    )
    completed_reassigned_batches = 0
    for reassignment_id in reassignment_ids:
        reassigned_ids = set(
            reassigned_for_user.loc[
                reassigned_for_user["reassignment_id"].astype(str)
                == reassignment_id,
                "message_id",
            ].astype(str)
        )
        if reassigned_ids and reassigned_ids.issubset(annotated_by_user):
            completed_reassigned_batches += 1

    pilot_batch_completed = (
        bool(pilot_ids)
        and pilot_ids.issubset(annotated_by_user)
    )

    is_formal_annotator = (
        str(annotator_id) in FORMAL_ANNOTATOR_ID_SET
    )

    released_formal_batches = (
        len(RELEASED_PARTICIPANT_BATCHES)
        if is_formal_annotator
        else 0
    )
    total_formal_batches = (
        TOTAL_PARTICIPANT_BATCHES
        if is_formal_annotator
        else 0
    )

    released_batch_count = (
        1
        + released_formal_batches
        + len(reassignment_ids)
    )
    total_batch_count = (
        1
        + total_formal_batches
        + len(reassignment_ids)
    )
    completed_batch_count = (
        int(pilot_batch_completed)
        + completed_main_batches
        + completed_reassigned_batches
    )

    with st.sidebar:
        st.metric(
            "Batches available",
            f"{released_batch_count}/{total_batch_count}",
        )
        st.metric(
            "Batches completed",
            f"{completed_batch_count}/{released_batch_count}",
        )
        st.metric("Prompts remaining", remaining_count)

        # if is_formal_annotator:
        #     st.caption(
        #         "The pilot is a testing batch."
        #     )
        # else:
        #     st.caption(
        #         "You currently have access only to the pilot testing batch."
        #     )

        st.divider()
        st.header("Support Resources")

        st.markdown(
            """
            Some messages may contain sensitive or distressing content.

            If you experience distress and would like support, SafeUT is available:

            https://safeut.org/
            """
        )

    pool = released_user_assignments[
        ~released_user_assignments["message_id"].isin(annotated_by_user)
    ].merge(
        messages,
        on=["message_id", "study_phase"],
        how="left",
    )

    pool["display_order"] = pool.apply(
        lambda row: (
            0
            if row["study_phase"] == "pilot"
            else (2 if bool(row.get("is_reassigned", False)) else 1)
        ),
        axis=1,
    )
    pool = pool.sort_values(
        ["display_order", "participant_batch_id", "reassignment_id", "message_id"]
    ).reset_index(drop=True)

    if pool.empty:
        st.success("You have completed all currently released assignments.")
        st.stop()

else:
    if not is_admin:
        st.warning("Enter the admin password in the sidebar to review samples.")
        st.stop()

    with st.sidebar:
        st.metric("Total samples", len(messages))
        st.metric("Total annotations", len(annotations))

    saved_annotation_ids = []

    if not annotations.empty and "annotator_id" in annotations.columns:
        saved_annotation_ids = (
            annotations["annotator_id"]
            .dropna()
            .astype(str)
            .str.strip()
            .str.lower()
            .unique()
            .tolist()
        )

    review_annotator_ids = sorted(
        set(FORMAL_ANNOTATOR_IDS) | set(saved_annotation_ids)
    )

    review_annotator = st.sidebar.selectbox(
        "Review annotator",
        ["All annotators"] + review_annotator_ids,
    )

    if review_annotator == "All annotators":
        review_options = ["All messages", "Pilot"]
    else:
        review_options = ["All assigned", "Pilot"] + [
            f"Personal batch {batch_id}"
            for batch_id in range(1, TOTAL_PARTICIPANT_BATCHES + 1)
        ]

    selected_review_batch = st.sidebar.selectbox(
        "Review phase / batch",
        review_options,
    )

    if review_annotator == "All annotators":
        if selected_review_batch == "Pilot":
            pool = messages[messages["study_phase"] == "pilot"].copy()
            pool["participant_batch_id"] = 0
        else:
            pool = messages.copy()
            pool["participant_batch_id"] = ""
    else:
        review_assignments = assignments[
            assignments["annotator_id"] == str(review_annotator)
        ].copy()

        if selected_review_batch == "Pilot":
            review_assignments = review_assignments[
                review_assignments["study_phase"] == "pilot"
            ]
        elif selected_review_batch.startswith("Personal batch"):
            selected_batch_id = int(selected_review_batch.split()[-1])
            review_assignments = review_assignments[
                (review_assignments["study_phase"] == "main")
                & (
                    review_assignments["participant_batch_id"]
                    == selected_batch_id
                )
            ]

        pool = review_assignments.merge(
            messages,
            on=["message_id", "study_phase"],
            how="left",
        )

    st.info(
        "Admin review mode: personal batch numbers belong to the selected "
        "annotator. Annotation controls are disabled."
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

if current["study_phase"] == "pilot":
    phase_label = "Pilot testing batch"
elif bool(current.get("is_reassigned", False)):
    phase_label = str(
        current.get("reassignment_batch_label", "Reassigned batch")
    )
else:
    phase_label = (
        f"Your main-study batch "
        f"{int(current['participant_batch_id'])} of {TOTAL_PARTICIPANT_BATCHES}"
    )

st.caption(phase_label)
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
                "study_phase",
                "batch_id",
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
        st.session_state["scroll_to_top"] = True
        st.rerun()

    if nav2.button("Next", use_container_width=True):
        st.session_state.current_message_id = pool_ids[
            (current_idx + 1) % len(pool_ids)
        ]
        st.session_state["scroll_to_top"] = True
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
        yes_labels = [
            category_id
            for category_id, decision in category_decisions.items()
            if decision == "Yes"
        ]

        maybe_labels = [
            category_id
            for category_id, decision in category_decisions.items()
            if decision == "Maybe"
        ]

        selected_or_maybe_labels = yes_labels + maybe_labels

        fallback_labels = {"GENERAL_LIFE_HELP_SEEKING", "OUT_OF_SCOPE"}
        selected_fallbacks = [
            label for label in selected_or_maybe_labels if label in fallback_labels
        ]

        selected_primary_labels = [
            label for label in selected_or_maybe_labels if label not in fallback_labels
        ]

        if not selected_or_maybe_labels:
            st.error(
                "Please select at least one category as Yes or Maybe. "
                "If none of the contextual categories apply, select General Life Help-Seeking or Out of Scope."
            )

        elif selected_primary_labels and selected_fallbacks:
            st.error(
                "General Life Help-Seeking and Out of Scope should only be used when none of the other contextual categories apply."
            )

        elif len(selected_fallbacks) > 1:
            st.error(
                "General Life Help-Seeking and Out of Scope are mutually exclusive. Please select only one."
            )

        else:
            row = {
                "message_id": str(current.get("message_id", "")),
                "conversation_id": str(current.get("conversation_id", "")),
                "first_user_message": str(current.get("first_user_message", "")),
                "annotator_id": str(annotator_id),
                "study_phase": str(current.get("study_phase", "")),
                "batch_id": int(current.get("participant_batch_id", 0)),
                "participation_type": (
                    "pilot_tester"
                    if str(current.get("study_phase", "")) == "pilot"
                    else "formal_annotator"
                ),
                "is_compensated_batch": (
                    str(current.get("study_phase", "")) != "pilot"
                ),
                "original_annotator_id": str(
                    current.get("original_annotator_id", annotator_id)
                ),
                "is_reassigned": bool(current.get("is_reassigned", False)),
                "reassignment_id": str(current.get("reassignment_id", "")),
                "labels": ";".join(yes_labels),
                "category_decisions": json.dumps(category_decisions),
                "notes": notes,
                "timestamp": utc_now_iso(),
            }

            save_annotation(row)
            st.cache_data.clear()

            remaining_ids = [
                message_id
                for message_id in pool_ids
                if message_id != str(current["message_id"])
            ]

            st.session_state.current_message_id = (
                remaining_ids[0] if remaining_ids else None
            )

            st.session_state["scroll_to_top"] = True
            st.rerun()