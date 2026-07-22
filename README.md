# Conversational Tax Assistant

A Streamlit app that interviews you in plain English about your income, job,
and life situation, then estimates your US federal tax liability using a
deterministic (non-AI) calculation engine.

## Features

- **Tax Chat Assistant** — a conversational interview (powered by [Groq](https://groq.com), free tier) that asks about income, expenses, and deductions, including a voice input option (speech transcribed via Groq's Whisper API).
- **Tax Dashboard & Summary** — a live breakdown of gross income, deductions found, taxable income, estimated tax liability (with a bracket-by-bracket explanation), and estimated refund/amount owed.
- **Deterministic tax engine** — applies the official 2026 single-filer federal tax brackets and standard deduction with plain arithmetic (no AI involved in the math), always choosing whichever of standard or itemized deductions saves you more.

## Setup

1. **Clone the repo and install dependencies:**

   ```bash
   git clone https://github.com/belagamkanchana-creator/conversational-tax-assistant.git
   cd conversational-tax-assistant
   pip install -r requirements.txt
   ```

2. **Get a free Groq API key:**

   - Go to [console.groq.com/keys](https://console.groq.com/keys)
   - Sign in and click **Create API Key** (no credit card required)

3. **Add your key:**

   ```bash
   cp .env.example .env
   ```

   Open `.env` and replace the placeholder with your real key:

   ```
   GROQ_API_KEY=gsk_your-actual-key-here
   ```

4. **Run the app:**

   ```bash
   streamlit run app.py
   ```

   This opens the app in your browser at `http://localhost:8501`.

## Project structure

| File | Purpose |
|---|---|
| `app.py` | Streamlit UI — chat page and dashboard page |
| `ai_agent.py` | Groq API integration — conversation, structured tax-data extraction, voice transcription |
| `tax_engine.py` | Deterministic 2026 federal tax bracket calculator (no AI) |
| `requirements.txt` | Python dependencies |
| `.env.example` | Template for your local `.env` file (never commit your real `.env`) |

## Disclaimer

This is a demo/learning project, not a substitute for real tax preparation
software or a licensed tax professional. It uses a simplified withholding
assumption and does not account for credits, state taxes, or many
real-world filing details.
