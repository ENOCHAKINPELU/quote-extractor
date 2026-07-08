# Quote Extraction Pipeline

## Overview

Supplier price quotes arrive as unstructured, free-form text: emails, PDFs
copy-pasted into a ticket, scanned order confirmations. Turning that text
into clean, structured data that a purchasing system can actually use is
tedious and error-prone to do by hand.

This project automates that process, end to end:

- **Loads** supplier quotes from a JSON input file.
- **Uses an LLM (Groq)** to extract structured fields — supplier name,
  currency, line items, pricing, lead times, and expiry — from raw text.
- **Validates** the LLM's output deterministically against a strict schema,
  because LLM output is never trusted blindly.
- **Normalizes** the validated data into a consistent format (currency
  casing, whitespace, lead-time units, etc.).
- **Determines whether a human needs to review** the quote, based on
  explicit, deterministic business rules.
- **Writes structured output** to disk, alongside a review summary and an
  audit log of every LLM call made.

The result is a pipeline where the LLM does the hard part — reading messy
text — and everything downstream of it is deterministic, testable, and
auditable.

## Architecture

The pipeline runs as a straight-line sequence of stages, each with a
single, narrow responsibility:

```
LOAD_INPUT
    ↓
LLM_EXTRACTION
    ↓
SCHEMA_VALIDATION
    ↓
NORMALIZATION
    ↓
REVIEW_DECISION
    ↓
RESULTS_WRITTEN
```

| Stage              | Responsibility                                                                                       | Module                  |
| ------------------- | ---------------------------------------------------------------------------------------------------- | ------------------------ |
| `LOAD_INPUT`        | Read the input JSON file and perform basic structural checks (correct shape, required keys present). | `pipeline/loader.py`     |
| `LLM_EXTRACTION`    | Send the raw quote text to an LLM and get back a structured (but untrusted) JSON dictionary.          | `llm/*`                  |
| `SCHEMA_VALIDATION` | Deterministically check the LLM's output against the expected schema and business rules.              | `pipeline/validator.py`  |
| `NORMALIZATION`     | Deterministically standardize values (currency casing, whitespace, lead-time units) without guessing. | `pipeline/normalizer.py` |
| `REVIEW_DECISION`   | Apply deterministic business rules to decide whether a human must review the quote, and why.          | `pipeline/reviewer.py`   |
| `RESULTS_WRITTEN`   | Persist the raw response, the final normalized quote, the review summary, and an LLM call log.        | `pipeline/writer.py`, `pipeline/logger.py` |

Each stage takes plain dictionaries in and returns plain dictionaries out.
No stage reaches into another stage's responsibility — validation never
normalizes, normalization never validates, and neither ever calls the LLM.

## Project Structure

```
quote_extractor/
│
├── main.py                # Application entry point; orchestrates the pipeline
├── config.py               # Environment configuration (.env loading, USE_MOCK, etc.)
├── requirements.txt         # Python dependencies
├── README.md                # This file
├── .env.example              # Template for required environment variables
├── quotes.json                # Input: supplier quotes to process
│
├── llm/                        # Provider-independent LLM layer
│   ├── adapter.py               # Abstract LLMAdapter interface
│   ├── groq_adapter.py           # Groq-backed implementation
│   └── mock_adapter.py            # Deterministic mock implementation (no API key needed)
│
├── pipeline/                       # The five deterministic pipeline stages
│   ├── loader.py                    # LOAD_INPUT
│   ├── validator.py                  # SCHEMA_VALIDATION
│   ├── normalizer.py                  # NORMALIZATION
│   ├── reviewer.py                     # REVIEW_DECISION
│   ├── writer.py                        # RESULTS_WRITTEN (JSON artifacts)
│   └── logger.py                         # RESULTS_WRITTEN (LLM call log)
│
├── models/                                # Pydantic v2 data contracts
│   └── schemas.py                          # Item / Quote models
│
├── outputs/                                 # Generated per-quote output (raw + final JSON)
│
├── tests/                                     # pytest test suite
│   ├── test_validator.py                       # Unit tests for validation rules
│   └── test_normalizer.py                        # Unit tests for normalization rules
│
├── review_summary.json                            # Generated: one entry per processed quote
└── llm_calls.jsonl                                  # Generated: append-only log of every LLM call
```

## Requirements

- **Python**: 3.11 or newer
- **Dependencies** (see `requirements.txt`):
  - `groq` — official Groq Python SDK
  - `pydantic` — data modeling and validation contracts
  - `python-dotenv` — environment variable loading
  - `pytest` — test runner
- **Groq API Key**: required unless running in [Mock Mode](#mock-mode).
  Get one from the [Groq console](https://console.groq.com/).

## Installation

### 1. Create and activate a virtual environment

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

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

Copy the example environment file and fill in your own values:

```bash
cp .env.example .env
```

| Variable       | Description                                          | Default                  |
| -------------- | ----------------------------------------------------- | -------------------------- |
| `GROQ_API_KEY` | Your Groq API key. Required unless `USE_MOCK=true`.    | _(none)_                  |
| `MODEL`        | The Groq model to use for extraction.                  | `llama-3.3-70b-versatile` |
| `USE_MOCK`     | If `true`, runs without calling the real Groq API.      | `false`                    |

### 4. Run the pipeline

```bash
python main.py --input quotes.json
```

Optional arguments:

```bash
python main.py --input quotes.json --output outputs/
```

| Argument   | Description                                             | Default        |
| ---------- | --------------------------------------------------------- | ---------------- |
| `--input`  | Path to the input quotes JSON file.                        | `quotes.json`   |
| `--output` | Directory to write per-quote output artifacts into.         | `outputs`        |

## Mock Mode

Setting `USE_MOCK=true` in `.env` lets the entire pipeline run without a
Groq API key or an internet connection. In this mode, every quote is
"extracted" using `llm/mock_adapter.py`, which returns fixed, deterministic
sample data instead of calling the real API.

This is useful for:

- Developing and testing the pipeline without burning API credits.
- Running the test suite and CI without secrets configured.
- Verifying the validation, normalization, and review stages in isolation.

The rest of the application never knows which adapter is in use — it only
ever calls `adapter.extract(text)` through the shared `LLMAdapter`
interface, so switching providers never requires touching pipeline code.

## Validation Rules

`pipeline/validator.py` deterministically checks the LLM's raw output
before anything else happens to it. Every rule is checked, even after an
earlier rule fails, so a single validation pass reports every problem at
once. Highlights:

- All required top-level keys must be present.
- `currency` must be `null` or a strict 3-letter uppercase code (e.g. `USD`).
- `items` must be a non-empty list.
- Each item requires `description`, `quantity` (a positive integer), and
  `unit_price` (a non-negative number); `sku` and `lead_time_days` may be
  `null`.
- `quote_expiry` must be `null` or a real calendar date in `YYYY-MM-DD`
  format — relative dates are never guessed at here.
- `shipping_included` and `needs_review` must be strict booleans.
- `notes` and `assumptions` must be lists of strings.

## Normalization Rules

`pipeline/normalizer.py` takes validated data and standardizes it,
deterministically and without guessing. Highlights:

- Whitespace is trimmed from every string field; `supplier_name` also
  collapses repeated internal spaces.
- `currency` is uppercased when it's a clean 3-letter code. Unambiguous
  symbols (`€`, `£`, `¥`) are mapped to their ISO code. A bare `$` is
  deliberately **not** mapped — it's shared by USD, CAD, AUD, and others,
  so guessing one would mean inventing a currency; it's left as-is for the
  review stage to flag instead. The LLM prompt itself is instructed to
  resolve `$`-style symbols from context (e.g. an explicit "USD" or
  "US dollars" mentioned nearby) wherever that's genuinely unambiguous.
- Textual lead times (`"2 weeks"`, `"5 days"`) are converted to integer
  days; values that can't be safely converted become `None` rather than
  guessed.
- `quote_expiry` is only whitespace-trimmed — relative dates like
  `"next Friday"` are left unresolved for the review stage to flag.
- `notes` and `assumptions` have every entry trimmed, with empty strings
  removed and order preserved.

## Output Files

| Path                              | Description                                                                                   |
| ---------------------------------- | ----------------------------------------------------------------------------------------------- |
| `outputs/{quote_id}_raw.json`       | The raw, unmodified dictionary returned by the LLM for that quote.                              |
| `outputs/{quote_id}.json`            | The final, validated, normalized quote, including the `needs_review` decision.                  |
| `review_summary.json`                | One entry per processed quote: `quote_id`, `needs_review`, `validation_errors`, `review_reasons`. |
| `llm_calls.jsonl`                      | An append-only audit log, one JSON object per line, of every LLM call made (never overwritten).  |

Each `llm_calls.jsonl` record's `status` is one of:

| Status              | Meaning                                                                                     |
| -------------------- | --------------------------------------------------------------------------------------------- |
| `success`            | Extraction, validation, and persistence all completed with no validation errors.              |
| `validation_failed`  | Extraction succeeded, but the LLM's output failed one or more schema/business rules.          |
| `parse_error`        | The LLM's response (or the data being written to disk) was not valid, usable JSON.            |
| `api_error`           | The request to the LLM provider itself failed (network, auth, rate limit, empty response).    |
| `unexpected_error`     | An unforeseen failure occurred outside the above categories (e.g. a disk write failure).       |

## Testing

The test suite covers the deterministic stages of the pipeline
(validation and normalization). It never calls the Groq API and never
makes network requests.

```bash
pytest
```

Run a specific file, or with verbose output:

```bash
pytest tests/test_validator.py -v
pytest tests/test_normalizer.py -v
```

## Design Decisions

**LLM extraction, validation, normalization, review, and persistence are
intentionally separated into distinct modules.** Each stage does exactly
one job and can be tested, reasoned about, and replaced independently:

- **Extraction** is the only stage that talks to a model, and it's hidden
  behind the `LLMAdapter` interface so the provider can change without any
  ripple effect elsewhere.
- **Validation** is deterministic and schema-driven. It never modifies
  data — it only reports what's wrong.
- **Normalization** is deterministic and narrow. It standardizes values it
  can standardize safely, and refuses to guess at ones it can't (a
  relative date, an unparseable lead time).
- **Review logic** is a separate set of business rules layered on top of
  validation and normalization output, deciding whether a human needs to
  look at a quote and why — without re-implementing validation or
  normalization itself.
- **Persistence** only serializes and writes; it contains no business
  logic at all.

The unifying principle behind this separation: **LLM output is always
treated as untrusted input.** No matter how good the prompt is, a model
can hallucinate a supplier name, invent a currency, or misread a date. By
routing every extraction through independent, deterministic validation and
normalization stages before any decision is made, the pipeline stays
predictable and auditable even when the model isn't perfect.

## Future Improvements

- **Async processing** — process multiple quotes concurrently instead of
  sequentially.
- **Batch inference** — batch multiple quotes into fewer LLM requests.
- **Retry strategy** — automatic retries with backoff for transient Groq
  API failures.
- **Database storage** — persist quotes and review decisions to a database
  instead of (or in addition to) flat files.
- **REST API** — expose the pipeline over HTTP instead of a CLI.
- **Observability** — structured logging, metrics, and tracing across
  pipeline stages.
- **Caching** — avoid re-extracting quotes whose input text hasn't
  changed.
