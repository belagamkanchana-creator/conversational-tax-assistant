"""
Conversation + extraction logic backed by the Groq API (free tier).

Two responsibilities live here, kept deliberately separate:

1. `get_assistant_reply` — a normal conversational turn where the model acts
   as a tax-interview assistant, asking about income, job, expenses, and
   life situation to surface deductions.
2. `extract_tax_profile` — a structured-output call that reads the full
   conversation so far and returns a strict JSON object with the user's
   current gross income and categorized deductions. This is run quietly
   after every user turn and cached into Streamlit session state.
"""

import json
import os

from dotenv import load_dotenv
from groq import Groq

load_dotenv()

MODEL_ID = "llama-3.3-70b-versatile"

_client = None


def get_client() -> Groq:
    """Lazily construct a single shared Groq client."""
    global _client
    if _client is None:
        api_key = os.environ.get("GROQ_API_KEY")
        _client = Groq(api_key=api_key)
    return _client


SYSTEM_PROMPT = """You are a friendly, thorough conversational tax assistant. \
Your job is to interview the user about their income and life situation to \
help them find every deduction they qualify for, the way an experienced tax \
preparer would.

Ask clear, specific follow-up questions, one topic at a time, to uncover:
- All sources of income (W-2 wages, 1099 self-employment, investments, etc.)
- Job-related and business expenses
- Student loan interest paid
- Charitable donations (cash and non-cash)
- Retirement contributions (401k, IRA)
- Health savings account (HSA) contributions
- Home office or self-employment expenses
- Dependents and life situation changes (marriage, kids, home purchase)

Keep your responses conversational and concise. Do not perform any tax math \
yourself and do not state a final refund or amount owed — a separate \
calculation engine handles that. Simply gather information and confirm your \
understanding back to the user."""


EXTRACTION_SYSTEM_PROMPT = """You extract structured tax data from a \
conversation between a user and a tax assistant. Read the full conversation \
and output the user's CURRENT best-known financial picture as JSON.

CRITICAL DISTINCTION — income vs. deductions:
- Money the user EARNED (salary, wages, freelance/1099 pay, business \
revenue, investment income, side-hustle income, etc.) is INCOME. Add every \
income source together into a single gross_income total. It must NEVER \
also appear inside deductions.
- Money the user SPENT or contributed (donations, student loan interest \
paid, retirement/HSA contributions, business or home-office expenses they \
paid out of pocket) is a DEDUCTION.
- A concrete test: if the number represents money flowing IN to the user, \
it's income. If it represents money flowing OUT of the user's pocket, it's \
a deduction. A freelance/1099 job's total earnings are income, not a \
"business_expenses" deduction — only actual costs the user paid to run \
that work (equipment, software, supplies, home office) are deductions.

Rules:
- gross_income is the sum of ALL income sources mentioned so far (W-2 \
wages + 1099/freelance/self-employment earnings + any other income). Use 0 \
if no income has been mentioned yet.
- deductions is a flat object mapping a short snake_case category name \
(e.g. "student_loan_interest", "charitable_giving", "business_expenses", \
"retirement_contributions", "hsa_contributions", "home_office") to the \
dollar amount the user stated they SPENT or contributed for that category.
- Only include deductions the user has actually stated a dollar amount for. \
Do not guess or invent figures, and never copy an income figure into \
deductions.
- If the same category is mentioned more than once, use the most recently \
stated (corrected) amount rather than summing duplicates.
- If nothing has been mentioned yet, return gross_income: 0 and an empty \
deductions object.

Respond with ONLY a raw JSON object in exactly this shape, no markdown \
fences, no commentary:
{"gross_income": <number>, "deductions": {"<category>": <number>, ...}}"""


def transcribe_audio(audio_bytes: bytes, filename: str = "recording.wav") -> str:
    """
    Transcribe a recorded voice message to text using Groq's free Whisper
    endpoint, so the user can talk instead of typing.
    """
    client = get_client()
    transcription = client.audio.transcriptions.create(
        file=(filename, audio_bytes),
        model="whisper-large-v3",
    )
    return (transcription.text or "").strip()


def get_assistant_reply(conversation_history: list[dict]) -> str:
    """
    Send the conversation so far to the model and return the assistant's
    next conversational message.

    conversation_history: list of {"role": "user"|"assistant", "content": str}
    """
    client = get_client()
    response = client.chat.completions.create(
        model=MODEL_ID,
        max_tokens=1024,
        messages=[{"role": "system", "content": SYSTEM_PROMPT}, *conversation_history],
    )
    return response.choices[0].message.content or ""


def extract_tax_profile(conversation_history: list[dict]) -> dict:
    """
    Analyze the conversation so far and return a structured dict:
    {"gross_income": float, "deductions": {category: amount, ...}}

    Uses Groq's JSON response mode so the output is machine-parseable rather
    than relying on scraping free-form text.
    """
    client = get_client()

    # Flatten the conversation into a single transcript for the extractor —
    # it only needs to read, not participate in, the dialogue.
    transcript = "\n".join(
        f"{turn['role'].upper()}: {turn['content']}" for turn in conversation_history
    )

    try:
        response = client.chat.completions.create(
            model=MODEL_ID,
            max_tokens=1024,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                {"role": "user", "content": transcript},
            ],
        )
        return json.loads(response.choices[0].message.content)
    except Exception:
        # If structured extraction fails for any reason, don't break the
        # chat experience — return an empty/default profile instead.
        return {"gross_income": 0, "deductions": {}}
