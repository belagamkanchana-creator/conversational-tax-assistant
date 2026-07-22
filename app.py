"""
Conversational Tax Assistant — Streamlit UI.

Page 1 (Tax Chat Assistant): a chat interface where the user describes their
income, job, expenses, and life situation in plain English. Claude interviews
them for deductions; a lightweight extraction call quietly keeps a structured
tax profile in session state after every turn.

Page 2 (Tax Dashboard & Summary): a visual breakdown of gross income,
deductions found, taxable income, and the estimated refund/amount owed,
computed by the deterministic tax_engine (no AI in the math).
"""

import streamlit as st

from ai_agent import extract_tax_profile, get_assistant_reply, transcribe_audio
from tax_engine import calculate_us_tax

st.set_page_config(
    page_title="Conversational Tax Assistant",
    page_icon="💬",
    layout="wide",
)

# Two pieces of positioning CSS, both keyed to Streamlit's `st.container(key=...)`
# class hook (`.st-key-<key>`):
#   1. The mic toggle button floats on the chat input's right edge, next to
#      its native send arrow — like ChatGPT/Claude's mic + send icons.
#   2. When recording, the mic is replaced entirely by the recorder row,
#      pinned in the same spot the chat input normally occupies — a full
#      inline swap rather than a floating popup.
# NOTE: offsets are fixed pixel values measured against the default
# (expanded) sidebar width; collapsing the sidebar may require retuning.
st.markdown(
    """
    <style>
    .st-key-mic_toggle_container {
        position: fixed !important;
        bottom: 56px;
        right: 128px;
        z-index: 999;
        width: fit-content !important;
    }
    .st-key-mic_toggle_container button {
        border: none !important;
        background: transparent !important;
        box-shadow: none !important;
        padding: 0.4rem !important;
        font-size: 1.2rem !important;
        min-height: 0 !important;
        border-radius: 50% !important;
    }
    .st-key-mic_toggle_container button:hover {
        background: rgba(128, 128, 128, 0.15) !important;
    }
    .st-key-mic_toggle_container button p {
        font-size: 1.2rem !important;
    }
    .st-key-voice_input_row {
        position: fixed !important;
        bottom: 12px;
        left: 336px !important;
        width: calc(100vw - 360px) !important;
        z-index: 999;
        background: var(--background-color, white);
        padding: 0.25rem 0.5rem;
        border-radius: 0.5rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def init_session_state():
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {
                "role": "assistant",
                "content": (
                    "Hi! I'm your tax assistant. Let's start with the basics — "
                    "what's your main source of income this year, and roughly "
                    "how much did you earn?"
                ),
            }
        ]
    if "tax_profile" not in st.session_state:
        st.session_state.tax_profile = {"gross_income": 0, "deductions": {}}


def render_sidebar() -> str:
    with st.sidebar:
        st.title("💬 Tax Assistant")
        st.caption("Talk it out. We'll do the math.")
        page = st.radio(
            "Navigate",
            ["Tax Chat Assistant", "Tax Dashboard & Summary"],
            label_visibility="collapsed",
        )
        st.divider()
        profile = st.session_state.tax_profile
        st.metric("Gross income (so far)", f"${profile['gross_income']:,.0f}")
        st.metric(
            "Deductions found",
            f"${sum(profile['deductions'].values()):,.0f}"
            if profile["deductions"]
            else "$0",
        )
        st.divider()
        if st.button("Reset conversation", use_container_width=True):
            st.session_state.clear()
            st.rerun()
    return page


def _safe_markdown(text: str) -> str:
    """Escape bare dollar signs so Streamlit doesn't interpret '$...$' pairs
    as LaTeX math (which mangles dollar amounts like "$95,000")."""
    return text.replace("$", "\\$")


def _handle_user_message(user_input: str):
    """Append a user message (typed or transcribed from voice), get the
    assistant's reply, and quietly refresh the extracted tax profile."""
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(_safe_markdown(user_input))

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            reply = get_assistant_reply(st.session_state.messages)
            st.markdown(_safe_markdown(reply))
    st.session_state.messages.append({"role": "assistant", "content": reply})

    # Quietly re-extract the structured tax profile from the updated
    # conversation and store it for the dashboard page.
    with st.spinner("Updating your tax profile..."):
        st.session_state.tax_profile = extract_tax_profile(st.session_state.messages)
    st.rerun()


def render_chat_page():
    st.session_state.setdefault("voice_mode", False)

    st.header("Tax Chat Assistant")
    st.caption(
        "Describe your income, job, expenses, and life situation. "
        "I'll ask follow-up questions to find deductions you qualify for."
    )

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(_safe_markdown(message["content"]))

    if st.session_state.voice_mode:
        # Full inline swap: the recorder takes the input bar's place
        # entirely, instead of opening in a separate floating popup.
        with st.container(key="voice_input_row"):
            cancel_col, recorder_col = st.columns([1, 12])
            with cancel_col:
                if st.button("✕", key="cancel_voice", help="Cancel"):
                    st.session_state.voice_mode = False
                    st.rerun()
            with recorder_col:
                audio_value = st.audio_input(
                    "Record your answer", label_visibility="collapsed"
                )

        if audio_value is not None:
            audio_bytes = audio_value.getvalue()
            audio_fingerprint = hash(audio_bytes)
            # audio_input keeps returning the same recording on every
            # rerun until cleared, so only transcribe new clips once.
            if audio_fingerprint != st.session_state.get("last_audio_fingerprint"):
                st.session_state.last_audio_fingerprint = audio_fingerprint
                st.session_state.voice_mode = False
                with st.spinner("Transcribing..."):
                    transcribed_text = transcribe_audio(audio_bytes)
                if transcribed_text:
                    _handle_user_message(transcribed_text)
                else:
                    st.warning("Couldn't make out any speech — try again.")
    else:
        with st.container(key="mic_toggle_container"):
            if st.button("🎤", key="mic_toggle", help="Talk instead of typing"):
                st.session_state.voice_mode = True
                st.rerun()

        user_input = st.chat_input("Tell me about your income, job, or expenses...")
        if user_input:
            _handle_user_message(user_input)


def render_dashboard_page():
    st.header("Tax Dashboard & Summary")

    profile = st.session_state.tax_profile
    gross_income = profile.get("gross_income", 0)
    deductions = profile.get("deductions", {})

    if not gross_income:
        st.info(
            "No income has come up in the chat yet. Head over to the "
            "**Tax Chat Assistant** page and tell me about your income to "
            "see your numbers here."
        )
        return

    result = calculate_us_tax(gross_income, deductions)

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Gross Income", f"${result['gross_income']:,.0f}")
    col2.metric(
        "Deductions Found",
        f"${result['itemized_deduction_total']:,.0f}",
        help="Sum of deductions extracted from your conversation.",
    )
    col3.metric("Taxable Income", f"${result['taxable_income']:,.0f}")
    col4.metric(
        "Tax Liability",
        f"${result['tax_liability']:,.0f}",
        help="Estimated federal tax owed before withholding, per the 2026 brackets.",
    )
    refund_label = "Estimated Refund" if result["is_refund"] else "Estimated Owed"
    col5.metric(refund_label, f"${abs(result['refund_or_owed']):,.0f}")

    with st.expander("See how the $%s tax liability was calculated" % f"{result['tax_liability']:,.0f}"):
        st.caption(
            "Your taxable income is taxed progressively — each bracket's "
            "rate only applies to the slice of income within that bracket."
        )
        for b in result["bracket_breakdown"]:
            upper = f"${b['upper_bound']:,.0f}" if b["upper_bound"] is not None else "and up"
            line = (
                f"- **{b['rate']*100:.0f}%** on income from "
                f"${b['lower_bound']:,.0f} to {upper} "
                f"→ ${b['amount_in_bracket']:,.0f} taxed → "
                f"**${b['tax_for_bracket']:,.2f}**"
            )
            st.markdown(_safe_markdown(line))
        st.markdown(_safe_markdown(f"**Total tax liability: ${result['tax_liability']:,.2f}**"))

    st.divider()

    left, right = st.columns([2, 1])

    with left:
        st.subheader("Income & Deduction Breakdown")
        chart_data = {
            "Gross Income": result["gross_income"],
            "Deduction Applied": result["deduction_used"],
            "Taxable Income": result["taxable_income"],
            "Tax Liability": result["tax_liability"],
        }
        st.bar_chart(chart_data)

        if deductions:
            st.subheader("Deductions by Category")
            st.bar_chart(deductions)

    with right:
        st.subheader("Details")
        deduction_type = (
            "Standard Deduction" if result["used_standard_deduction"] else "Itemized Deductions"
        )
        st.write(f"**Deduction method used:** {deduction_type}")
        st.write(f"**Standard deduction:** ${result['standard_deduction']:,.0f}")
        st.write(f"**Itemized total:** ${result['itemized_deduction_total']:,.0f}")
        st.caption(
            "We automatically apply whichever deduction — standard or "
            "itemized — saves you the most money."
        )
        st.write(f"**Estimated withholding:** ${result['estimated_withholding']:,.0f}")

        if deductions:
            st.write("**Deduction categories found:**")
            for category, amount in deductions.items():
                st.write(f"- {category.replace('_', ' ').title()}: ${amount:,.0f}")

    st.divider()
    if result["is_refund"]:
        st.success(
            f"Based on what you've told me, you're on track for an estimated "
            f"refund of **${result['refund_or_owed']:,.0f}**."
        )
    else:
        st.warning(
            f"Based on what you've told me, you may owe an estimated "
            f"**${abs(result['refund_or_owed']):,.0f}**."
        )


def main():
    init_session_state()
    page = render_sidebar()
    if page == "Tax Chat Assistant":
        render_chat_page()
    else:
        render_dashboard_page()


if __name__ == "__main__":
    main()
