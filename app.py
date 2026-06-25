import html
import streamlit as st

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

ALLOWED_EXPERT_IDS = {
    "u6045151",
    "u1655162",
    "1",
    "2",
    "3",
}


def mark_instructions_complete():
    expert_id = st.session_state.get("home_expert_id", "").strip()

    if not expert_id:
        st.session_state["instructions_error"] = "Please enter your Expert ID / UNID."
        return

    if expert_id not in ALLOWED_EXPERT_IDS:
        st.session_state["instructions_error"] = (
            "Invalid Expert ID. Please check your assigned Expert ID and try again."
        )
        return

    if not st.session_state.get("read_definitions_checkbox", False):
        st.session_state["instructions_error"] = (
            "Please read the category definitions and check the acknowledgement box before continuing."
        )
        return

    acknowledged_ids = load_acknowledgements()

    if expert_id not in acknowledged_ids:
        save_acknowledgement(
            {
                "annotator_id": expert_id,
                "timestamp": utc_now_iso(),
            }
        )

    st.session_state["verified_annotator"] = expert_id
    st.session_state["instructions_acknowledged"] = True
    st.session_state["instructions_read_by"] = expert_id
    st.session_state["instructions_error"] = ""


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


with st.expander("Annotation Task", expanded=True):
    st.markdown(
        """
Our goal is to understand **what kinds of help-seeking questions people bring to LLMs**.

You will review the **first message** that a user sent in a conversation with an LLM and identify the
context of the user's request.

The primary annotation scheme consists of **eight contextual categories** adapted from the DSM-5 section **"Other Conditions That May Be a Focus of Clinical Attention."** These categories describe psychosocial, environmental, relational, occupational, legal, health-service, and other contextual conditions that may be relevant to a person's situation. **They are not mental disorder diagnoses.**

In addition to these eight contextual categories, the annotation scheme also includes **General Life Help-Seeking** and **Out of Scope**.
"""
    )


with st.expander("Instructions", expanded=True):
    st.markdown(
        """
Please read the definition of **each category at least once** before starting annotation.

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

    with st.expander("Annotation Instructions", expanded=True):
        st.markdown(
            """
1. Open the **Annotate** page from the sidebar.
2. Enter your **Expert ID / UNID** if prompted.
3. Ensure you are in **Annotation** mode. The **Review** mode is intended for administrators only.
4. Read the **user message** carefully.
5. For each contextual category:
   - Select **Yes** if the category clearly applies.
   - Select **Maybe** if the category may apply but you are uncertain.
   - Leave both options unselected if the category does **not** apply.
6. Select **all categories that apply**. A message may belong to multiple categories.
7. Select **General Life Help-Seeking** only when the message is clearly seeking guidance or advice but does **not** fit any of the other contextual categories.
   - **General Life Help-Seeking** should **not** be selected together with any other category.
8. Select **Out of Scope** only when the message is **not** a personal help-seeking request, or when none of the contextual categories, including **General Life Help-Seeking**, apply.
   - **Out of Scope** is **mutually exclusive** and must not be selected together with any other category.
9. Use the optional **Notes / rationale** field to explain your reasoning, especially for ambiguous or borderline cases, or to provide any additional context that may be helpful.
"""
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


with st.container(border=True):
    #st.subheader("Acknowledge Instructions")

    st.text_input(
        "Expert ID / UNID",
        placeholder="e.g. u1234567",
        key="home_expert_id",
    )

    st.checkbox(
        "I have read the category definitions and instructions before beginning annotation.",
        key="read_definitions_checkbox",
    )

    st.button(
        "Save acknowledgement",
        type="primary",
        use_container_width=True,
        on_click=mark_instructions_complete,
    )

    if st.session_state.get("instructions_error"):
        st.error(st.session_state["instructions_error"])

    elif st.session_state.get("verified_annotator"):
        st.success(
            f"Instructions acknowledged for **{st.session_state['verified_annotator']}**. "
            "You may now open the Annotate page from the sidebar."
        )


if not st.session_state.get("verified_annotator"):
    st.warning(
        "Please enter your Expert ID / UNID, read the category definitions, and save the acknowledgement before annotating."
    )
else:
    st.info("Use the sidebar navigation to start annotating.")