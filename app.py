import base64
import html
import re
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from utils.styles import apply_styles, hero
from utils.io import (
    load_messages,
    load_annotations,
    load_taxonomy,
    load_acknowledgements,
    save_acknowledgement,
    utc_now_iso,
)

st.set_page_config(
    page_title="Help-Seeking Context Annotation",
    page_icon="📝",
    layout="wide",
)

apply_styles()

messages = load_messages()
annotations = load_annotations()
taxonomy = load_taxonomy()

# ALLOWED_EXPERT_IDS = {
#     "u6045151",
#     "u1655162",
#     "1",
#     "2",
#     "3",
# }
UNID_PATTERN = re.compile(r"^u\d{7}$", re.IGNORECASE)


# Replace the PDF at this location with the final IRB-stamped document.
# Keep the same filename, or update this path if you rename the file.
CONSENT_PDF_PATH = Path("assets/consent_letter.pdf")

def normalize_unid(value: str) -> str | None:
    """
    Normalize and validate a University of Utah uNID.

    A valid uNID consists of the letter 'u' followed by exactly seven digits.
    """
    unid = value.strip().lower()

    if not UNID_PATTERN.fullmatch(unid):
        return None

    return unid

def mark_instructions_complete():
    entered_id = st.session_state.get("home_expert_id", "")
    expert_id = normalize_unid(entered_id)

    if expert_id is None:
        st.session_state["instructions_error"] = (
            "Please enter a valid University of Utah uNID in the format "
            "u followed by 7 digits, such as u1234567."
        )
        return

    if not st.session_state.get("study_acknowledgement_checkbox", False):
        st.session_state["instructions_error"] = (
            "Please review the study information, consent document, category "
            "definitions, and instructions, then check the acknowledgement box "
            "before continuing."
        )
        return

    acknowledged_ids = load_acknowledgements()

    if expert_id not in acknowledged_ids:
        save_acknowledgement(
            {
                "annotator_id": expert_id,
                "timestamp": utc_now_iso(),
                "acknowledgement_type": "study_consent",
            }
        )

    # Store the normalized uNID everywhere.
    st.session_state["home_expert_id"] = expert_id
    st.session_state["verified_annotator"] = expert_id
    st.session_state["instructions_acknowledged"] = True
    st.session_state["instructions_read_by"] = expert_id
    st.session_state["instructions_error"] = ""



def display_pdf(pdf_path: Path, height: int = 850):
    """Display a local PDF inside the Streamlit page."""
    if not pdf_path.exists():
        st.error(
            "The IRB-approved consent PDF could not be found. "
            f"Expected location: {pdf_path.as_posix()}"
        )
        return False

    st.pdf(
        pdf_path,
        height=height,
    )

    return True

    pdf_bytes = pdf_path.read_bytes()
    encoded_pdf = base64.b64encode(pdf_bytes).decode("utf-8")

    components.html(
        f"""
        <iframe
            src="data:application/pdf;base64,{encoded_pdf}#toolbar=1&navpanes=0"
            width="100%"
            height="{height}px"
            style="border: 1px solid #D1D5DB; border-radius: 10px;"
            title="IRB-approved study information and consent document">
        </iframe>
        """,
        height=height + 20,
        scrolling=True,
    )
    return True


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
        '<div style="padding-right:0.6rem; font-size:0.95rem;">'
        + "".join(html_parts)
        + "</div>"
    )


hero(
    "Help-Seeking Context Annotation",
"")


with st.expander("Study Information and Consent", expanded=True):
    st.markdown(
        """
Please read the study information and consent document below
before continuing.
"""
    )
    consent_pdf_available = display_pdf(CONSENT_PDF_PATH)


with st.expander("Annotation Task", expanded=True):
    st.markdown(
        """
Our goal is to understand **what kinds of help-seeking questions people bring to LLMs**.

You will review the **first message** that a user sent in a conversation with an LLM and identify the
context of the user's request.

The primary annotation scheme consists of **nine contextual categories** adapted from the DSM-5 section **"Other Conditions That May Be a Focus of Clinical Attention."** These categories describe psychosocial, environmental, relational, occupational, legal, health-service, and other contextual conditions that may be relevant to a person's situation. **They are not mental disorder diagnoses.**

In addition to these nine contextual categories, the annotation scheme also includes **General Life Help-Seeking** and **Out of Scope**.
"""
    )


with st.expander("Instructions", expanded=True):
    st.markdown(
        """
Please read the instructions and definition of **each category at least once** before starting annotation.

Try to set aside any assumptions about what the category names mean. Some labels may sound intuitive,
but for this task you should rely on the provided definitions and examples.
"""
    )

    with st.expander("Category Definitions", expanded=False):
        for item in taxonomy:
            with st.expander(item["label"], expanded=False):
                st.markdown(
                    format_definition(item["definition"]),
                    unsafe_allow_html=True,
                )

    with st.expander("Annotation Instructions", expanded=False):
#         st.markdown(
#             """
# 1. Open the **Annotate** page from the sidebar.
# 2. Enter your **Expert ID / UNID** if prompted.
# 3. Ensure you are in **Annotation** mode. The **Review** mode is intended for administrators only.
# 4. Read the **user message** carefully.
# 5. For each contextual category:
#    - Select **Yes** if the category clearly applies.
#    - Select **Maybe** if the category may apply but you are uncertain.
#    - Leave both options unselected if the category does **not** apply.
# 6. Select **all categories that apply**. A message may belong to multiple categories.
# 7. Select **General Life Help-Seeking** only when the message is clearly seeking guidance or advice but does **not** fit any of the other contextual categories.
#    - **General Life Help-Seeking** should **not** be selected together with any other category.
# 8. Select **Out of Scope** only when the message is **not** a personal help-seeking request, or when none of the contextual categories, including **General Life Help-Seeking**, apply.
#    - **Out of Scope** is **mutually exclusive** and must not be selected together with any other category.
# 9. Use the optional **Notes / rationale** field to explain your reasoning, especially for ambiguous or borderline cases, or to provide any additional context that may be helpful.
# """
#         )
        st.markdown(
    """
1. Open the **Annotate** page from the sidebar.
2. Enter your **Expert ID / UNID** if prompted.
3. Ensure you are in **Annotation** mode. The **Review** mode is intended for administrators only.
4. Read the **user message** carefully.
5. For each contextual category:

<div style="background:#F8FAFC; border-left:5px solid #64748B; padding:0.9rem 1rem; border-radius:0.6rem; margin:1rem 0;">
Select <b>Yes</b> if the category clearly applies.<br>
Select <b>Maybe</b> if the category may apply but you are uncertain.<br>
<span style="background:#FEF3C7; padding:0.15rem 0.35rem; border-radius:0.35rem; font-weight:700;">
Leave both options unselected if the category does not apply.
</span>
</div>

6. Select **all categories that apply**. A message may belong to multiple categories.
7. General Life Help-Seeking

<div style="background:#EFF6FF; border-left:5px solid #3B82F6; padding:0.9rem 1rem; border-radius:0.6rem; margin:1rem 0;">
Select this only when the message is clearly seeking guidance or advice but does <b>not</b> fit any of the other contextual categories.<br>
<b>Do not select this together with any other category.</b>
</div>
8. Out of Scope

<div style="background:#FEF2F2; border-left:5px solid #EF4444; padding:0.9rem 1rem; border-radius:0.6rem; margin:1rem 0;">
Select this only when the message is <b>not</b> a personal help-seeking request, or when none of the contextual categories, including General Life Help-Seeking, apply.<br>
<b>Out of Scope is mutually exclusive and must not be selected together with any other category.</b>
</div>

9. Use the optional **Notes / rationale** field to explain your reasoning, especially for ambiguous or borderline cases.
""",
    unsafe_allow_html=True,
)


with st.expander("Examples", expanded=False):
    st.markdown(
        """
**Example 1**

**User message:**  
*I keep arguing with my partner and I don't know how to fix things between us.*

**Good label:**  
- Relational Problems — **Yes**

**Why:**  
The user is seeking help about conflict in a close relationship.

---

**Example 2**

**User message:**  
*I lost my job and I'm worried I won't be able to pay rent next month.*

**Good labels:**  
- Educational / Occupational Problems — **Yes**
- Housing / Economic Problems — **Yes**

**Why:**  
The message involves both job loss and financial/housing insecurity.

---

**Example 3**

**User message:**  
*Write me a Python function to sort a list.*

**Good label:**  
- Out of Scope — **Yes**

**Why:**  
This is a task request, not a personal help-seeking or life-context dilemma.
"""
    )

st.warning(
    """
    **Content Warning**

    This annotation task involves reviewing de-identified user messages from real-world conversations.
    Some messages may contain discussions of sensitive topics, including relationship difficulties,
    abuse, trauma, mental health concerns, self-harm, suicide, grief, financial hardship, or other
    potentially distressing situations.

    Participation is voluntary. If you believe that viewing this type of content may be distressing
    or triggering, please do not continue. You may stop participation at any time without penalty.

    If you experience distress during the study and would like support, please consider contacting
    an appropriate mental health resource. For participants, support is available through
    SafeUT: https://safeut.org/
    """
)

st.info(
    """
    **Pilot testing access**

    The pilot annotation batch is available to anyone with a valid University
    of Utah uNID.

    Access to later formal annotation batches will be limited to selected
    annotators.
    """
)

with st.container(border=True):
    #st.subheader("Acknowledge Instructions")

    st.text_input(
    "University of Utah uNID",
    placeholder="e.g. u1234567",
    key="home_expert_id",
    max_chars=8,
    help="Enter the letter u followed by your 7-digit University ID.",
    )

    st.checkbox(
    "I have read the study information and consent document, reviewed the "
    "category definitions and instructions, and voluntarily agree to participate "
    "in this research study.",
    key="study_acknowledgement_checkbox",
    disabled=not consent_pdf_available,
    )

    st.button(
        "Save acknowledgement",
        type="primary",
        use_container_width=True,
        on_click=mark_instructions_complete,
    )

    if st.session_state.get("instructions_error"):
        st.error(st.session_state["instructions_error"])

    # elif st.session_state.get("verified_annotator"):
    #     st.success(
    #         #f"Instructions acknowledged for **{st.session_state['verified_annotator']}**. "
    #         #"You may now open the Annotate page from the sidebar."
    #     )


if not st.session_state.get("verified_annotator"):
    st.warning(
        "Please enter your University of Utah uNID, review the consent document "
        "and category definitions, and save the acknowledgement before continuing."
    )
else:
    st.markdown(
        """
        <div style="text-align:center; padding:1.5rem 0 0.5rem 0;">
            <h3 style="margin-bottom:0.25rem;">✅ You're ready to begin</h3>
            <p style="margin-top:0;">Thank you for reviewing the instructions and category definitions.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2, c3 = st.columns([2, 3, 2])

    with c2:
        if st.button(
            "🚀 Start Annotation",
            type="primary",
            use_container_width=True,
        ):
            st.switch_page("pages/1_Annotate.py")