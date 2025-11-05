#!/usr/bin/env python3

import asyncio
from pathlib import Path

from ocr import OCRProcessor


async def main():
    # Example 1: Using the new OCRProcessor class directly
    print("=== Example 1: Using OCRProcessor directly ===")
    processor = OCRProcessor(provider_name="mistral")

    # Process a single file
    sample_file = Path("samples/gpt-paper.pdf")
    if sample_file.exists():
        print(f"Processing file: {sample_file}")
        text = await processor.aprocess_file(sample_file)
        if text:
            print(f"Successfully extracted {len(text)} characters of text")
        else:
            print("Failed to process file")
    else:
        print(f"Sample file not found: {sample_file}")

    # Example 4: Show supported providers
    print("\n=== Example 4: Supported providers ===")
    providers = processor.get_supported_providers()
    print(f"Available OCR providers: {providers}")


if __name__ == "__main__":
    asyncio.run(main())
