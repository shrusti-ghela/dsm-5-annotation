import streamlit as st


def apply_styles() -> None:
    st.markdown(
        """
        <style>
        .stApp {
            background: #faf7f2;
            color: #2b2621;
        }
        .block-container {
            padding-top: 2rem;
            padding-bottom: 3rem;
            max-width: 1180px;
        }
        .hero {
            padding: 1.35rem 1.55rem;
            border-radius: 22px;
            background: linear-gradient(135deg, #fff7ed 0%, #f4efff 100%);
            border: 1px solid #eadfd2;
            margin-bottom: 1.1rem;
            box-shadow: 0 8px 24px rgba(80, 55, 30, 0.06);
        }
        .hero h1 {
            margin: 0;
            font-size: 2rem;
            letter-spacing: -0.03em;
        }
        .hero p {
            margin: 0.4rem 0 0 0;
            color: #6b5f55;
            font-size: 1rem;
        }
        .card {
            padding: 1.15rem 1.35rem;
            border-radius: 20px;
            border: 1px solid #e6ddd3;
            background: #fffaf4;
            margin-bottom: 1rem;
            box-shadow: 0 4px 14px rgba(80, 55, 30, 0.045);
        }
        .user-card {
            background: #fff1e6;
            border-left: 7px solid #e9a66f;
        }
        .info-card {
            background: #f3edff;
            border-left: 7px solid #a78bfa;
        }
        .metric-card {
            background: #fffaf4;
            padding: 1rem;
            border-radius: 18px;
            border: 1px solid #e6ddd3;
        }
        .pill {
            display: inline-block;
            padding: 0.28rem 0.7rem;
            margin: 0.15rem 0.18rem 0.15rem 0;
            border-radius: 999px;
            background: #efe7dc;
            color: #46382e;
            font-size: 0.82rem;
            font-weight: 600;
        }
        .muted {
            color: #776b62;
            font-size: 0.9rem;
        }
        div[data-testid="stSidebar"] {
            background: #fffaf4;
            border-right: 1px solid #eadfd2;
        }
        .stButton > button {
            border-radius: 999px;
            border: 1px solid #d7c7b7;
            font-weight: 700;
        }
        .stDownloadButton > button {
            border-radius: 999px;
            border: 1px solid #d7c7b7;
            font-weight: 700;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def hero(title: str, subtitle: str) -> None:
    st.markdown(
        f"""
        <div class="hero">
            <h1>{title}</h1>
            <p>{subtitle}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def card(html: str, variant: str = "card") -> None:
    st.markdown(f'<div class="card {variant}">{html}</div>', unsafe_allow_html=True)


def pills(labels: list[str]) -> str:
    return " ".join([f'<span class="pill">{label}</span>' for label in labels])
