# DSM-5 Help-Seeking Annotation App

A lightweight Streamlit app for annotating first-user messages using DSM-5 psychosocial/contextual categories.

## What is included

```text
app.py
pages/
  1_Annotate.py
  2_Review_Disagreements.py
  3_Export_Stats.py
utils/
  agreement.py
  io.py
  styles.py
data/
  input_messages.csv
  annotations.csv
taxonomy/
  dsm_categories.json
requirements.txt
.streamlit/config.toml
```

## Input data format

Replace `data/input_messages.csv` with your real first-user-message data.

Required columns:

```csv
message_id,first_user_message
```

Recommended columns:

```csv
message_id,conversation_id,first_user_message,model,country,state,timestamp_utc
```

## Run locally

From inside this folder:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

On Windows PowerShell, activate with:

```powershell
.venv\Scripts\Activate.ps1
```

## Annotation output

Annotations are saved to:

```text
data/annotations.csv
```

Each row contains:

```text
message_id
conversation_id
first_user_message
annotator_id
labels
confidence
unclear
notes
timestamp
taxonomy_version
```

Labels are saved as semicolon-separated values, for example:

```text
RELATIONAL_PROBLEMS;ABUSE_NEGLECT
```

## Notes

- Multi-label annotation is supported.
- `OUT_OF_SCOPE` cannot be combined with in-scope categories.
- The review page finds exact label-set disagreements across annotators.
- The stats page computes simple label distribution, exact agreement, and Cohen's kappa when exactly two annotators are present.
