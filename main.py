"""Entry point for the Quote Extraction Pipeline.

Orchestrates the full pipeline for every quote in an input file:

    LOAD_INPUT -> LLM_EXTRACTION -> SAVE_RAW_OUTPUT -> SCHEMA_VALIDATION ->
    NORMALIZATION -> REVIEW_DECISION -> SAVE_FINAL_OUTPUT -> LOG_LLM_CALL ->
    WRITE_REVIEW_SUMMARY

All business logic (validation rules, normalization rules, review rules,
JSON parsing) lives in the pipeline modules; this file only sequences
calls to them and keeps a running review summary.
"""

import argparse
import sys

import config
from llm.adapter import LLMAdapter
from pipeline.loader import InputFileError, InvalidQuoteFormatError, load_quotes
from pipeline.logger import log_llm_call
from pipeline.normalizer import normalize_quote
from pipeline.reviewer import determine_review
from pipeline.validator import validate_quote
from pipeline.writer import OutputWriteError, SerializationError, save_final_output, save_raw_output, write_review_summary


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for the pipeline entry point."""
    parser = argparse.ArgumentParser(description="Quote Extraction Pipeline")
    parser.add_argument(
        "--input",
        default="quotes.json",
        help="Path to the input quotes JSON file (default: quotes.json)",
    )
    parser.add_argument(
        "--output",
        default="outputs",
        help="Directory to write output artifacts to (default: outputs)",
    )
    return parser.parse_args()


def select_adapter() -> tuple[LLMAdapter, str]:
    """Choose the LLM adapter to use, based on config.USE_MOCK.

    Every other part of the pipeline interacts with the returned adapter
    only through the LLMAdapter interface, so it never knows (or needs to
    know) which provider is actually in use.

    Returns:
        A tuple of (adapter instance, human-readable provider name).
    """
    if config.USE_MOCK:
        from llm.mock_adapter import MockAdapter

        return MockAdapter(), "Mock"

    from llm.groq_adapter import GroqAdapter

    return GroqAdapter(), "Groq"


def build_summary_entry(
    quote_id: str,
    needs_review: bool,
    validation_errors: list[str],
    review_reasons: list[str],
) -> dict:
    """Build one review_summary record for a processed (or failed) quote."""
    return {
        "quote_id": quote_id,
        "needs_review": needs_review,
        "validation_errors": validation_errors,
        "review_reasons": review_reasons,
    }


def process_quote(
    record: dict,
    adapter: LLMAdapter,
    provider_name: str,
    input_path: str,
    output_dir: str,
) -> dict:
    """Run one quote record through the full pipeline.

    Never raises: any failure at any stage is captured as a review summary
    entry and a logged call, so the caller can continue with the next
    quote regardless of what went wrong with this one.

    Args:
        record: A quote record with "id" and "text" keys, as returned by load_quotes.
        adapter: The LLM adapter to use for extraction.
        provider_name: Human-readable provider name, for logging.
        input_path: Path to the input file, for logging.
        output_dir: Directory to write output artifacts to.

    Returns:
        A review_summary entry for this quote.
    """
    quote_id = record["id"]
    output_artifact = ""

    print(f"Processing {quote_id}...")

    try:
        try:
            raw_response = adapter.extract(record["text"])
        except Exception as exc:
            reason = f"LLM extraction failed: {exc}"
            print(f"  {reason}")
            log_llm_call(quote_id, provider_name, config.MODEL, input_path, output_artifact, "api_error")
            return build_summary_entry(quote_id, True, [], [reason])

        try:
            raw_path = save_raw_output(quote_id, raw_response, output_dir=output_dir)
            output_artifact = str(raw_path)
        except SerializationError as exc:
            reason = f"Raw LLM output could not be serialized: {exc}"
            print(f"  {reason}")
            log_llm_call(quote_id, provider_name, config.MODEL, input_path, output_artifact, "parse_error")
            return build_summary_entry(quote_id, True, [], [reason])
        except OutputWriteError as exc:
            reason = f"Failed to save raw output: {exc}"
            print(f"  {reason}")
            log_llm_call(quote_id, provider_name, config.MODEL, input_path, output_artifact, "unexpected_error")
            return build_summary_entry(quote_id, True, [], [reason])

        validated_data, validation_errors = validate_quote(raw_response)
        print("  Validation passed" if not validation_errors else "  Validation failed")

        normalized_quote = normalize_quote(validated_data)
        review_result = determine_review(normalized_quote, validation_errors)
        normalized_quote["needs_review"] = review_result["needs_review"]

        try:
            final_path = save_final_output(quote_id, normalized_quote, output_dir=output_dir)
            output_artifact = str(final_path)
            print(f"  Saved {final_path}")
        except SerializationError as exc:
            reason = f"Final quote could not be serialized: {exc}"
            print(f"  {reason}")
            log_llm_call(quote_id, provider_name, config.MODEL, input_path, output_artifact, "parse_error")
            return build_summary_entry(
                quote_id, True, validation_errors, review_result["review_reasons"] + [reason]
            )
        except OutputWriteError as exc:
            reason = f"Failed to save final output: {exc}"
            print(f"  {reason}")
            log_llm_call(quote_id, provider_name, config.MODEL, input_path, output_artifact, "unexpected_error")
            return build_summary_entry(
                quote_id, True, validation_errors, review_result["review_reasons"] + [reason]
            )

        status = "validation_failed" if validation_errors else "success"
        log_llm_call(quote_id, provider_name, config.MODEL, input_path, output_artifact, status)

        return build_summary_entry(
            quote_id,
            review_result["needs_review"],
            validation_errors,
            review_result["review_reasons"],
        )

    except Exception as exc:  # last-resort safety net: one bad record must not stop the run
        reason = f"Unexpected error: {exc}"
        print(f"  {reason}")
        log_llm_call(quote_id, provider_name, config.MODEL, input_path, output_artifact, "unexpected_error")
        return build_summary_entry(quote_id, True, [], [reason])


def main() -> None:
    """Run the Quote Extraction Pipeline end-to-end."""
    args = parse_args()
    adapter, provider_name = select_adapter()

    print("Loading quotes...")
    try:
        quotes = load_quotes(args.input)
    except (InputFileError, InvalidQuoteFormatError) as exc:
        print(f"Failed to load input file '{args.input}': {exc}")
        sys.exit(1)

    review_summary = [
        process_quote(record, adapter, provider_name, args.input, args.output) for record in quotes
    ]

    try:
        write_review_summary(review_summary)
    except (OutputWriteError, SerializationError) as exc:
        print(f"Failed to write review summary: {exc}")
        sys.exit(1)

    print("Processing complete.")


if __name__ == "__main__":
    main()
