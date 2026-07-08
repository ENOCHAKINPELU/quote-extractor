# Quote Extractor

An AI-powered pipeline that extracts structured quote data (speaker, quote
text, and context) from raw text documents using the Groq API.

## Overview

This project takes unstructured text containing embedded quotations and uses
a large language model, served via Groq, to identify and extract each quote
along with its attributed speaker and surrounding context. The output is
returned as structured, validated data using Pydantic models.

> **Status:** Project scaffolding only. The extraction pipeline and LLM
> integration have not been implemented yet.

## Folder Structure

```
quote_extractor/
│
├── main.py              # Application entry point
├── config.py             # Environment/configuration loading
├── requirements.txt       # Python dependencies
├── README.md              # Project documentation
├── .env.example           # Template for required environment variables
├── quotes.json            # Sample input data
│
├── llm/                   # Groq API client and prompt logic
│   └── __init__.py
│
├── pipeline/              # Extraction pipeline orchestration
│   └── __init__.py
│
├── models/                # Pydantic data models
│   └── __init__.py
│
├── outputs/                # Generated pipeline outputs
│
├── tests/                  # Test suite
│   └── __init__.py
│
└── llm_calls.jsonl         # Log of raw LLM requests/responses
```

## Installation

### 1. Clone or download the project

```bash
cd quote_extractor
```

### 2. Create and activate a virtual environment

**Windows (PowerShell):**

```powershell
python -m venv venv
venv\Scripts\Activate.ps1
```

**macOS / Linux:**

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

## Environment Configuration

Copy the example environment file and fill in your own values:

```bash
cp .env.example .env
```

Configure the following variables in `.env`:

| Variable       | Description                                         | Default                       |
| -------------- | ---------------------------------------------------- | ------------------------------ |
| `GROQ_API_KEY` | Your Groq API key. Required unless `USE_MOCK=true`.   | _(none)_                       |
| `MODEL`        | The Groq model to use for extraction.                | `llama-3.3-70b-versatile`      |
| `USE_MOCK`     | If `true`, runs without calling the real Groq API.    | `false`                        |

## Running the Application

> Placeholder — the extraction pipeline is not implemented yet.

```bash
python main.py
```

## Architecture

_To be documented once the pipeline is implemented._

## Validation

_To be documented once Pydantic models and validation rules are implemented._

## Normalization

_To be documented once quote/text normalization logic is implemented._

## Testing

_To be documented once the test suite is implemented._

```bash
pytest
```
