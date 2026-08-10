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
    get_annotation,
    is_batch_submitted,
    submit_batch,
    save_annotation,
    utc_now_iso,
)

st.set_page_config(page_title="Annotate", page_icon="📝", layout="wide")
apply_styles()

st.markdown(
    """
    <style>
    /* Main user-message card */
    .annotation-user-message {
        background: linear-gradient(135deg, #FFF4E8 0%, #FFE4C2 100%);
        border: 1px solid #F3A34A;
        border-left: 8px solid #E97816;
        border-radius: 14px;
        padding: 1.35rem 1.5rem;
        margin: 0.65rem 0 1.8rem 0;
        box-shadow: 0 8px 22px rgba(190, 104, 25, 0.12);
    }

    .annotation-user-message-label {
        color: #A84B00;
        font-size: 0.82rem;
        font-weight: 750;
        letter-spacing: 0.04em;
        margin-bottom: 0.55rem;
        text-transform: uppercase;
    }

    .annotation-user-message-text {
        color: #17212B;
        font-size: 1.08rem;
        line-height: 1.65;
        margin: 0;
        overflow-wrap: anywhere;
    }

    /* Category headings should remain smaller than section headings */
    .annotation-category-heading {
        display: flex;
        align-items: center;
        gap: 0.6rem;
        min-height: 2.3rem;
        margin-top: 1rem;
        margin-bottom: 0.15rem;
        padding: 0.45rem 0.65rem;
        border-left: 5px solid var(--category-color);
        border-radius: 5px;
        background: rgba(127, 127, 127, 0.06);
    }

    .annotation-category-dot {
        width: 0.72rem;
        height: 0.72rem;
        border-radius: 50%;
        background: var(--category-color);
        flex-shrink: 0;
    }

    .annotation-category-label {
        color: inherit;
        font-size: 0.98rem;
        font-weight: 700;
        line-height: 1.3;
    }

    [data-testid="stMainBlockContainer"] h2 {
        font-size: 1.35rem;
        margin-top: 1.2rem;
        margin-bottom: 0.3rem;
    }

    [data-testid="stCaptionContainer"] {
        font-size: 0.86rem;
    }

    [data-testid="stExpander"] summary {
        font-size: 0.9rem;
        font-weight: 600;
    }

    [data-testid="stCheckbox"] label p {
        font-size: 0.92rem;
    }

    [data-testid="stExpander"] {
        margin-bottom: 0.45rem;
    }

    /* Notes section */
    .annotation-notes-heading {
        display: flex;
        align-items: center;
        gap: 0.55rem;
        margin-top: 1.7rem;
        margin-bottom: 0.45rem;
        padding: 0.75rem 0.9rem;
        border-radius: 10px;
        background: #FFF8E7;
        border: 1px solid #E7B85C;
        border-left: 6px solid #D98B00;
        font-weight: 750;
        font-size: 1rem;
        color: #6B4300;
    }

    .annotation-notes-help {
        margin: -0.1rem 0 0.55rem 0;
        color: #5D6470;
        font-size: 0.88rem;
    }

    [data-testid="stTextArea"] {
        padding: 0.85rem 0.9rem 0.95rem 0.9rem;
        border-radius: 12px;
        background: #FFFDF8;
        border: 1px solid #E8C985;
        box-shadow: 0 4px 14px rgba(105, 79, 23, 0.07);
        margin-bottom: 1rem;
    }

    [data-testid="stTextArea"] textarea {
        min-height: 130px;
        border: 1.5px solid #D9A441 !important;
        border-radius: 9px !important;
        background: #FFFFFF !important;
        font-size: 0.95rem !important;
        line-height: 1.55 !important;
    }

    [data-testid="stTextArea"] textarea:focus {
        border-color: #C87800 !important;
        box-shadow: 0 0 0 3px rgba(216, 139, 0, 0.14) !important;
    }

    [data-testid="stTextArea"] label p {
        font-weight: 700;
        color: #4C3A16;
    }

    /* Slightly soften the full page and improve section rhythm */
    [data-testid="stMainBlockContainer"] {
        padding-top: 1.4rem;
        padding-bottom: 3rem;
    }

    div[data-testid="stVerticalBlock"] > div:has(.annotation-category-heading) {
        scroll-margin-top: 1rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

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

# Color-blind-friendly category accents based on the Okabe-Ito palette.
# Color is used as a secondary visual cue; category names remain visible.
CATEGORY_COLORS = {
    "RELATIONAL_PROBLEMS": "#0072B2",
    "EDUCATIONAL_OCCUPATIONAL_PROBLEMS": "#E69F00",
    "HOUSING_ECONOMIC_PROBLEMS": "#009E73",
    "SOCIAL_ENVIRONMENT_PROBLEMS": "#CC79A7",
    "LEGAL_CRIME_PROBLEMS": "#D55E00",
    "HEALTH_SERVICE_ENCOUNTERS": "#56B4E9",
    "OTHER_PSYCHOSOCIAL_ENVIRONMENTAL_PROBLEMS": "#F0B000",
    "PERSONAL_HISTORY": "#6A51A3",
    "ABUSE_NEGLECT": "#B2182B",
    "GENERAL_LIFE_HELP_SEEKING": "#4D4D4D",
    "OUT_OF_SCOPE": "#767676",
}
DEFAULT_CATEGORY_COLOR = "#5F6B76"


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
        '<div style="max-height:520px; overflow-y:auto; padding-right:0.6rem; font-size:0.9rem;">'
        + "".join(html_parts)
        + "</div>"
    )


ADMIN_PASSWORD = st.secrets.get("ADMIN_PASSWORD", "admin123")

# -----------------------------------------------------------------------------
# STUDY / PARTICIPANT-BATCH CONFIGURATION
# -----------------------------------------------------------------------------
# Configure how many of the 100 main-study prompts each formal annotator receives.
# Rules enforced below:
#   1. Exactly four formal annotators are configured.
#   2. Counts must sum to 200 total annotations.
#   3. No annotator can receive more than 100 prompts.
#   4. Every main-study prompt is assigned to exactly two DIFFERENT annotators.
#
# Example below means:
#   - u1509787 gets all 100 prompts.
#   - u1276376 gets 0 main-study prompts for now.
#   - u1588664 and u1589107 each get 50 prompts.
# The 50-prompt assignments are non-overlapping, so every prompt has two annotators.
ANNOTATOR_PROMPT_COUNTS = {
    "u1589107": 100,
    "u1276376": 0,
    "u1588664": 50,
    "u1509787": 50,
}

FORMAL_ANNOTATOR_IDS = list(ANNOTATOR_PROMPT_COUNTS.keys())
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
REQUIRED_ANNOTATIONS_PER_PROMPT = 2
REQUIRED_TOTAL_MAIN_ANNOTATIONS = (
    MAIN_STUDY_SIZE * REQUIRED_ANNOTATIONS_PER_PROMPT
)


def validate_assignment_configuration() -> None:
    """Fail early when the configured annotation counts cannot satisfy the study."""
    if len(FORMAL_ANNOTATOR_IDS) != 4:
        raise ValueError(
            "Exactly four formal annotators must be configured in "
            "ANNOTATOR_PROMPT_COUNTS."
        )

    if len(FORMAL_ANNOTATOR_ID_SET) != len(FORMAL_ANNOTATOR_IDS):
        raise ValueError("Formal annotator uNIDs must be unique.")

    invalid_ids = [
        annotator_id
        for annotator_id in FORMAL_ANNOTATOR_IDS
        if not UNID_PATTERN.fullmatch(str(annotator_id))
    ]
    if invalid_ids:
        raise ValueError(f"Invalid formal annotator uNIDs: {invalid_ids}")

    invalid_counts = {
        annotator_id: count
        for annotator_id, count in ANNOTATOR_PROMPT_COUNTS.items()
        if not isinstance(count, int) or count < 0 or count > MAIN_STUDY_SIZE
    }
    if invalid_counts:
        raise ValueError(
            "Each prompt count must be an integer between 0 and "
            f"{MAIN_STUDY_SIZE}: {invalid_counts}"
        )

    configured_total = sum(ANNOTATOR_PROMPT_COUNTS.values())
    if configured_total != REQUIRED_TOTAL_MAIN_ANNOTATIONS:
        raise ValueError(
            "ANNOTATOR_PROMPT_COUNTS must sum to exactly "
            f"{REQUIRED_TOTAL_MAIN_ANNOTATIONS} annotations, but currently sums "
            f"to {configured_total}."
        )


validate_assignment_configuration()


def build_prompt_annotator_pairs() -> list[tuple[str, str]]:
    """
    Build one pair of distinct annotators for each of the 100 main-study prompts.

    The requested count for every annotator is respected exactly. At each prompt,
    the two annotators with the largest remaining assignment counts are selected.
    Ties follow FORMAL_ANNOTATOR_IDS order, making the assignment deterministic.

    For the configuration 100 / 0 / 50 / 50, this naturally produces:
      - the 100-count annotator on every prompt;
      - the two 50-count annotators on disjoint halves of the prompts.
    """
    remaining = dict(ANNOTATOR_PROMPT_COUNTS)
    order = {annotator_id: idx for idx, annotator_id in enumerate(FORMAL_ANNOTATOR_IDS)}
    pairs: list[tuple[str, str]] = []

    for prompt_idx in range(MAIN_STUDY_SIZE):
        prompts_left = MAIN_STUDY_SIZE - prompt_idx

        # A participant cannot still need more assignments than there are prompts left.
        impossible = {
            annotator_id: count
            for annotator_id, count in remaining.items()
            if count > prompts_left
        }
        if impossible:
            raise ValueError(
                "The configured prompt counts cannot be distributed with two distinct "
                f"annotators per prompt. Remaining counts: {remaining}"
            )

        candidates = [
            annotator_id
            for annotator_id in FORMAL_ANNOTATOR_IDS
            if remaining[annotator_id] > 0
        ]
        candidates.sort(
            key=lambda annotator_id: (
                -remaining[annotator_id],
                order[annotator_id],
            )
        )

        if len(candidates) < REQUIRED_ANNOTATIONS_PER_PROMPT:
            raise ValueError(
                "Could not assign two distinct annotators to every prompt. "
                f"Remaining counts: {remaining}"
            )

        selected = candidates[:REQUIRED_ANNOTATIONS_PER_PROMPT]
        pairs.append((selected[0], selected[1]))

        for annotator_id in selected:
            remaining[annotator_id] -= 1

    if any(remaining.values()):
        raise ValueError(
            "Assignment generation did not consume all configured counts: "
            f"{remaining}"
        )

    generated_counts = {annotator_id: 0 for annotator_id in FORMAL_ANNOTATOR_IDS}
    for pair in pairs:
        if len(set(pair)) != REQUIRED_ANNOTATIONS_PER_PROMPT:
            raise ValueError(f"Prompt received duplicate annotators: {pair}")
        for annotator_id in pair:
            generated_counts[annotator_id] += 1

    if generated_counts != ANNOTATOR_PROMPT_COUNTS:
        raise ValueError(
            "Generated assignments do not match ANNOTATOR_PROMPT_COUNTS. "
            f"Expected {ANNOTATOR_PROMPT_COUNTS}, got {generated_counts}."
        )

    if len(pairs) != MAIN_STUDY_SIZE:
        raise ValueError(
            f"Expected {MAIN_STUDY_SIZE} prompt pairs, got {len(pairs)}."
        )

    return pairs


MAIN_ASSIGNMENT_PAIRS = build_prompt_annotator_pairs()


def build_batch_sizes(prompt_count: int) -> list[int]:
    """Split an annotator's assigned prompts into batches of roughly 7-8 prompts."""
    prompt_count = int(prompt_count)

    if prompt_count <= 0:
        return []

    # Use the fewest batches possible while keeping each batch at no more than 8.
    number_of_batches = (prompt_count + 7) // 8
    base_size, remainder = divmod(prompt_count, number_of_batches)

    # Put the slightly larger batches first. For example:
    #   50  -> [8, 7, 7, 7, 7, 7, 7]
    #   100 -> nine 8s + four 7s (13 batches total)
    return [base_size + 1] * remainder + [base_size] * (number_of_batches - remainder)


def get_participant_batch_sizes(annotator_id: str) -> list[int]:
    """Return the configured main-study batch sizes for one formal annotator."""
    annotator_id = str(annotator_id).strip().lower()
    prompt_count = int(ANNOTATOR_PROMPT_COUNTS.get(annotator_id, 0))
    return build_batch_sizes(prompt_count)


def get_total_participant_batches(annotator_id: str) -> int:
    """Return how many main-study batches the annotator has."""
    return len(get_participant_batch_sizes(annotator_id))


# Access / release policy. These are intentionally independent controls.
#
# PILOT_ACCESS:
#   Annotators listed here can access the 8-prompt pilot.
#
# MAIN_RELEASED:
#   Annotators listed here can access ALL main-study prompts assigned to them
#   by ANNOTATOR_PROMPT_COUNTS. Main-study access is NOT automatically released
#   when the pilot is completed; you control release explicitly here.
#
# Example current state:
#   - u1509787: pilot + 100 main prompts
#   - u1276376: no pilot and no main prompts
#   - u1588664: pilot only; their 50 main prompts are still locked
#   - u1589107: pilot only; their 50 main prompts are still locked
PILOT_ACCESS = {
    "u1509787",
    "u1588664",
    "u1589107",
}

MAIN_RELEASED = {
    "u1589107",
}


def validate_access_configuration() -> None:
    """Validate pilot and main-study access settings."""
    unknown_pilot = set(PILOT_ACCESS) - FORMAL_ANNOTATOR_ID_SET
    if unknown_pilot:
        raise ValueError(
            f"PILOT_ACCESS contains unknown formal annotators: {sorted(unknown_pilot)}"
        )

    unknown_main = set(MAIN_RELEASED) - FORMAL_ANNOTATOR_ID_SET
    if unknown_main:
        raise ValueError(
            f"MAIN_RELEASED contains unknown formal annotators: {sorted(unknown_main)}"
        )


validate_access_configuration()


def get_released_participant_batches(annotator_id: str) -> set[int]:
    """Return explicitly released main-study batches for one annotator."""
    annotator_id = str(annotator_id).strip().lower()

    if annotator_id not in FORMAL_ANNOTATOR_ID_SET:
        return set()

    if annotator_id not in MAIN_RELEASED:
        return set()

    total_batches = get_total_participant_batches(annotator_id)
    return set(range(1, total_batches + 1))


# Optional reassignment rules. Leave this empty unless needed.
# Each rule transfers only unfinished prompts from one participant batch.
# Candidate replacements are tried in order. A candidate is skipped when they
# are already assigned to, or have already annotated, that message.
REASSIGNMENT_RULES = []


def assign_personal_batches(main_df):
    """
    Create configurable annotator-specific assignments and personal batches.

    Every main-study prompt is assigned to exactly two different formal annotators.
    Each annotator receives exactly the number of prompts configured in
    ANNOTATOR_PROMPT_COUNTS. Their prompts are then divided into roughly 7-8 item
    batches, balanced by message character length.
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
            for main_idx, pair in enumerate(MAIN_ASSIGNMENT_PAIRS)
            if annotator_id in pair
        ]

        expected_count = ANNOTATOR_PROMPT_COUNTS[annotator_id]
        if len(assigned_indices) != expected_count:
            raise ValueError(
                f"Annotator {annotator_id} has {len(assigned_indices)} generated "
                f"assignments instead of configured count {expected_count}."
            )

        if not assigned_indices:
            continue

        participant_batch_sizes = get_participant_batch_sizes(annotator_id)
        total_participant_batches = len(participant_batch_sizes)
        released_batches = get_released_participant_batches(annotator_id)

        batch_total_lengths = [0] * total_participant_batches
        batch_counts = [0] * total_participant_batches
        batch_for_index = {}

        longest_first = sorted(
            assigned_indices,
            key=lambda idx: (-message_lengths[idx], idx),
        )

        for main_idx in longest_first:
            eligible_batches = [
                batch_idx
                for batch_idx, target_size in enumerate(participant_batch_sizes)
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

        if batch_counts != participant_batch_sizes:
            raise ValueError(
                f"Batch construction failed for {annotator_id}. Expected "
                f"{participant_batch_sizes}, got {batch_counts}."
            )

        for main_idx in assigned_indices:
            participant_batch_id = int(batch_for_index[main_idx])

            assignments.append(
                {
                    "message_id": str(main_df.iloc[main_idx]["message_id"]),
                    "annotator_id": str(annotator_id),
                    "study_phase": "main",
                    "participant_batch_id": participant_batch_id,
                    "is_released": participant_batch_id in released_batches,
                    "original_annotator_id": str(annotator_id),
                    "is_reassigned": False,
                    "reassignment_id": "",
                    "reassignment_batch_label": "",
                }
            )

    # Final study-level safety checks.
    assignments_df = pd.DataFrame(assignments)

    if len(assignments_df) != REQUIRED_TOTAL_MAIN_ANNOTATIONS:
        raise ValueError(
            f"Expected {REQUIRED_TOTAL_MAIN_ANNOTATIONS} main-study assignments, "
            f"got {len(assignments_df)}."
        )

    counts_by_message = assignments_df.groupby("message_id")["annotator_id"].nunique()
    if len(counts_by_message) != MAIN_STUDY_SIZE or not (
        counts_by_message == REQUIRED_ANNOTATIONS_PER_PROMPT
    ).all():
        raise ValueError(
            "Every main-study message must be assigned to exactly two distinct annotators."
        )

    return assignments

def prepare_study(messages_df):
    """
    Prepare the 8-message pilot and 100-message main study.

    Expected row order:
      rows 0-7   = pilot
      rows 8-107 = main study

    Pilot assignments are added dynamically after a participant logs in.
    Main-study assignments follow ANNOTATOR_PROMPT_COUNTS, with exactly
    two distinct annotators assigned to every main-study message.
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
    assignment_rows = assign_personal_batches(main_df)

    return study_messages, assignment_rows


def add_pilot_assignments(
    assignments_df: pd.DataFrame,
    messages_df: pd.DataFrame,
    annotator_id: str,
) -> pd.DataFrame:
    """
    Give pilot access only to annotators explicitly listed in PILOT_ACCESS.

    Main-study assignments and release are controlled separately.
    """
    updated = assignments_df.copy()
    annotator_id = str(annotator_id).strip().lower()

    if annotator_id not in PILOT_ACCESS:
        return updated

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
        source_total_batches = get_total_participant_batches(from_annotator)
        if participant_batch_id not in range(1, source_total_batches + 1):
            raise ValueError(
                f"Invalid participant_batch_id {participant_batch_id} for "
                f"annotator {from_annotator}; they have {source_total_batches} "
                f"main-study batches. Reassignment: {reassignment_id}."
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


def get_yes_maybe_decision(
    annotator_id,
    message_id,
    category_id,
    saved_decision="No",
):
    """Render mutually exclusive Yes/Maybe checkboxes with saved values loaded."""
    key_prefix = f"{annotator_id}_{message_id}_{category_id}"
    yes_key = f"{key_prefix}_yes"
    maybe_key = f"{key_prefix}_maybe"

    normalized_saved = (
        saved_decision
        if saved_decision in {"Yes", "Maybe", "No"}
        else "No"
    )

    if yes_key not in st.session_state:
        st.session_state[yes_key] = normalized_saved == "Yes"

    if maybe_key not in st.session_state:
        st.session_state[maybe_key] = normalized_saved == "Maybe"

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

            has_pilot_access = annotator_id in PILOT_ACCESS
            has_main_access = annotator_id in MAIN_RELEASED

            if has_pilot_access and has_main_access:
                st.caption(
                    "You have access to the pilot and your currently released "
                    "formal annotation batches."
                )
            elif has_pilot_access:
                st.caption("You currently have access to the pilot testing batch.")
            elif has_main_access:
                st.caption("You currently have access to your released formal annotation batches.")
            else:
                st.caption("No annotation batches are currently released for this uNID.")

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

    # Build the released batches in display order. A submitted batch is locked
    # and is no longer available for annotation.
    released_batches = []

    pilot_rows = released_user_assignments[
        released_user_assignments["study_phase"] == "pilot"
    ].copy()

    if not pilot_rows.empty:
        released_batches.append(
            {
                "study_phase": "pilot",
                "batch_id": 0,
                "label": "Pilot testing batch",
                "rows": pilot_rows,
            }
        )

    normal_main_rows = released_user_assignments[
        (released_user_assignments["study_phase"] == "main")
        & (~released_user_assignments["is_reassigned"].astype(bool))
    ].copy()

    for batch_id in sorted(
        normal_main_rows["participant_batch_id"].dropna().astype(int).unique()
    ):
        batch_rows = normal_main_rows[
            normal_main_rows["participant_batch_id"].astype(int) == int(batch_id)
        ].copy()

        released_batches.append(
            {
                "study_phase": "main",
                "batch_id": int(batch_id),
                "label": (
                    f"Your main-study batch {int(batch_id)} "
                    f"of {get_total_participant_batches(str(annotator_id))}"
                ),
                "rows": batch_rows,
            }
        )

    # Reassigned batches are kept separate in the interface. The current
    # configuration has no reassignment rules, but this preserves compatibility.
    reassigned_rows = released_user_assignments[
        released_user_assignments["is_reassigned"].astype(bool)
    ].copy()

    for reassignment_id in sorted(
        reassigned_rows["reassignment_id"].dropna().astype(str).unique()
    ):
        if not reassignment_id:
            continue

        batch_rows = reassigned_rows[
            reassigned_rows["reassignment_id"].astype(str) == reassignment_id
        ].copy()

        if batch_rows.empty:
            continue

        batch_id = int(batch_rows.iloc[0]["participant_batch_id"])

        released_batches.append(
            {
                "study_phase": "main",
                "batch_id": batch_id,
                "label": str(
                    batch_rows.iloc[0].get(
                        "reassignment_batch_label",
                        f"Reassigned batch {reassignment_id}",
                    )
                ),
                "rows": batch_rows,
            }
        )

    for batch in released_batches:
        batch["submitted"] = is_batch_submitted(
            annotator_id=str(annotator_id),
            study_phase=batch["study_phase"],
            batch_id=batch["batch_id"],
        )

    unlocked_batches = [
        batch for batch in released_batches if not batch["submitted"]
    ]

    completed_batch_count = sum(
        1 for batch in released_batches if batch["submitted"]
    )

    is_formal_annotator = (
        str(annotator_id) in FORMAL_ANNOTATOR_ID_SET
    )

    released_formal_batches = (
        len(get_released_participant_batches(str(annotator_id)))
        if is_formal_annotator
        else 0
    )

    total_formal_batches = (
        get_total_participant_batches(str(annotator_id))
        if is_formal_annotator
        else 0
    )

    reassignment_count = len(
        [
            batch
            for batch in released_batches
            if batch["label"].startswith("Reassigned batch")
        ]
    )

    released_batch_count = len(released_batches)
    total_batch_count = (
        1 + total_formal_batches + reassignment_count
    )

    remaining_count = 0
    for batch in unlocked_batches:
        batch_ids = set(batch["rows"]["message_id"].astype(str))
        remaining_count += len(batch_ids - annotated_by_user)

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

        st.divider()
        st.header("Support Resources")

        st.markdown(
            """
            Some messages may contain sensitive or distressing content.

            If you experience distress and would like support, SafeUT is available:

            https://safeut.org/
            """
        )

    if not released_batches:
        st.info("No annotation batches are currently available.")
        st.stop()

    if not unlocked_batches:
        st.success("You have submitted all currently released batches.")
        st.stop()

    # Work through one complete batch at a time. Saved prompts remain in the
    # pool so annotators can use Previous and edit them until final submission.
    active_batch = unlocked_batches[0]
    active_batch_key = (
        active_batch["study_phase"],
        active_batch["batch_id"],
        active_batch["label"],
    )

    if st.session_state.get("active_batch_key") != active_batch_key:
        st.session_state["active_batch_key"] = active_batch_key
        st.session_state["current_message_id"] = None

    pool = active_batch["rows"].merge(
        messages,
        on=["message_id", "study_phase"],
        how="left",
    )

    pool = pool.sort_values("message_id").reset_index(drop=True)
    active_batch_label = active_batch["label"]
    active_study_phase = active_batch["study_phase"]
    active_batch_id = active_batch["batch_id"]

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
        review_total_batches = get_total_participant_batches(str(review_annotator))
        review_options = ["All assigned", "Pilot"] + [
            f"Personal batch {batch_id}"
            for batch_id in range(1, review_total_batches + 1)
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

if mode == "Annotation":
    # Resume each active batch at the first prompt that has not yet been saved.
    # Previously saved prompts remain in `pool_ids`, so annotators can still use
    # Previous to revisit and edit them before submitting the batch.
    unfinished_ids = [
        message_id
        for message_id in pool_ids
        if message_id not in annotated_by_user
    ]

    resume_batch_key = (
        str(annotator_id),
        str(active_study_phase),
        int(active_batch_id),
        str(active_batch_label),
    )

    # Increment this value whenever the resume behavior changes. This forces
    # existing Streamlit sessions to adopt the newest initialization logic.
    RESUME_LOGIC_VERSION = 2

    should_initialize_resume_position = (
        st.session_state.get("resume_batch_key") != resume_batch_key
        or st.session_state.get("resume_logic_version")
        != RESUME_LOGIC_VERSION
        or st.session_state.get("current_message_id") not in pool_ids
    )

    if should_initialize_resume_position:
        st.session_state["resume_batch_key"] = resume_batch_key
        st.session_state["resume_logic_version"] = RESUME_LOGIC_VERSION
        st.session_state["current_message_id"] = (
            unfinished_ids[0]
            if unfinished_ids
            else pool_ids[-1]
        )

else:
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
        f"{int(current['participant_batch_id'])} of "
        f"{get_total_participant_batches(str(annotator_id))}"
    )

st.caption(phase_label)
st.markdown(
    f"""
    <section class="annotation-user-message" aria-label="User message">
        <div class="annotation-user-message-label">User message</div>
        <p class="annotation-user-message-text">{safe_msg}</p>
    </section>
    """,
    unsafe_allow_html=True,
)


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
    current_idx = pool_ids.index(str(current["message_id"]))
    current_message_id = str(current["message_id"])

    saved_annotation = get_annotation(
        annotator_id=str(annotator_id),
        message_id=current_message_id,
    )

    saved_decisions = {}
    saved_notes = ""

    if saved_annotation:
        saved_decisions = saved_annotation.get(
            "category_decisions",
            {},
        )

        if isinstance(saved_decisions, str):
            try:
                saved_decisions = json.loads(saved_decisions)
            except json.JSONDecodeError:
                saved_decisions = {}

        if not isinstance(saved_decisions, dict):
            saved_decisions = {}

        saved_notes = str(saved_annotation.get("notes", ""))

    st.caption(
        f"Prompt {current_idx + 1} of {len(pool_ids)} · {active_batch_label}"
    )

    st.subheader("Context Categories")
    st.caption(
        "Select Yes if the category clearly applies, Maybe if uncertain, "
        "or leave both unchecked if it does not apply."
    )

    category_decisions = {}

    for item in taxonomy:
        category_id = str(item["id"])
        category_label = html.escape(str(item["label"]))
        category_color = CATEGORY_COLORS.get(
            category_id,
            DEFAULT_CATEGORY_COLOR,
        )

        st.markdown(
            f"""
            <div
                class="annotation-category-heading"
                style="--category-color: {category_color};"
            >
                <span
                    class="annotation-category-dot"
                    aria-hidden="true"
                ></span>
                <span class="annotation-category-label">
                    {category_label}
                </span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        decision = get_yes_maybe_decision(
            annotator_id=str(annotator_id),
            message_id=current_message_id,
            category_id=category_id,
            saved_decision=saved_decisions.get(category_id, "No"),
        )

        category_decisions[category_id] = decision

        with st.expander(
            f"View definition for {item['label']}",
            expanded=False,
        ):
            st.markdown(
                format_definition(item["definition"]),
                unsafe_allow_html=True,
            )

    notes_key = f"{annotator_id}_{current_message_id}_notes"

    if notes_key not in st.session_state:
        st.session_state[notes_key] = saved_notes

    st.markdown(
        """
        <div class="annotation-notes-heading">
            <span aria-hidden="true">✍️</span>
            <span>Notes / rationale</span>
        </div>
        <div class="annotation-notes-help">
            Optional: briefly explain uncertain, overlapping, or difficult category choices.
        </div>
        """,
        unsafe_allow_html=True,
    )

    notes = st.text_area(
        "Notes / rationale",
        placeholder="Add an optional note about your reasoning...",
        key=notes_key,
        height=140,
        label_visibility="collapsed",
    )

    is_last_prompt = current_idx == len(pool_ids) - 1
    previous_col, action_col = st.columns(2)

    with previous_col:
        previous_clicked = st.button(
            "← Previous",
            use_container_width=True,
            disabled=current_idx == 0,
        )

    with action_col:
        action_clicked = st.button(
            "Submit batch" if is_last_prompt else "Save & Next →",
            type="primary",
            use_container_width=True,
        )

    if previous_clicked:
        st.session_state.current_message_id = pool_ids[current_idx - 1]
        st.session_state["scroll_to_top"] = True
        st.rerun()

    if action_clicked:
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

        fallback_labels = {
            "GENERAL_LIFE_HELP_SEEKING",
            "OUT_OF_SCOPE",
        }

        selected_fallbacks = [
            label
            for label in selected_or_maybe_labels
            if label in fallback_labels
        ]

        selected_primary_labels = [
            label
            for label in selected_or_maybe_labels
            if label not in fallback_labels
        ]

        validation_error = None

        if not selected_or_maybe_labels:
            validation_error = (
                "Please select at least one category as Yes or Maybe. "
                "If none of the contextual categories apply, select "
                "General Life Help-Seeking or Out of Scope."
            )

        elif selected_primary_labels and selected_fallbacks:
            validation_error = (
                "General Life Help-Seeking and Out of Scope should only "
                "be used when none of the other contextual categories apply."
            )

        elif len(selected_fallbacks) > 1:
            validation_error = (
                "General Life Help-Seeking and Out of Scope are mutually "
                "exclusive. Please select only one."
            )

        if validation_error:
            st.error(validation_error)

        else:
            row = {
                "message_id": current_message_id,
                "conversation_id": str(
                    current.get("conversation_id", "")
                ),
                "first_user_message": str(
                    current.get("first_user_message", "")
                ),
                "annotator_id": str(annotator_id),
                "study_phase": str(active_study_phase),
                "batch_id": int(active_batch_id),
                "participation_type": (
                    "pilot_tester"
                    if str(active_study_phase) == "pilot"
                    else "formal_annotator"
                ),
                "is_compensated_batch": (
                    str(active_study_phase) != "pilot"
                ),
                "original_annotator_id": str(
                    current.get(
                        "original_annotator_id",
                        annotator_id,
                    )
                ),
                "is_reassigned": bool(
                    current.get("is_reassigned", False)
                ),
                "reassignment_id": str(
                    current.get("reassignment_id", "")
                ),
                "labels": ";".join(yes_labels),
                "maybe_labels": ";".join(maybe_labels),
                "category_decisions": json.dumps(
                    category_decisions
                ),
                "notes": notes,
                "timestamp": utc_now_iso(),
            }

            save_annotation(row)

            if is_last_prompt:
                refreshed_annotations = load_annotations()

                completed_ids = set(
                    refreshed_annotations.loc[
                        refreshed_annotations["annotator_id"].astype(str)
                        == str(annotator_id),
                        "message_id",
                    ].astype(str)
                )

                missing_ids = set(pool_ids) - completed_ids

                if missing_ids:
                    st.error(
                        "Every prompt in this batch must be saved before "
                        "the batch can be submitted."
                    )
                    st.stop()

                submit_batch(
                    annotator_id=str(annotator_id),
                    study_phase=str(active_study_phase),
                    batch_id=int(active_batch_id),
                )

                st.session_state["current_message_id"] = None
                st.session_state["active_batch_key"] = None
                st.session_state["scroll_to_top"] = True
                st.success(
                    "Batch submitted successfully. It is now locked "
                    "and can no longer be edited."
                )
                st.rerun()

            st.session_state.current_message_id = pool_ids[
                current_idx + 1
            ]
            st.session_state["scroll_to_top"] = True
            st.rerun()
