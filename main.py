"""
[DEV] Atlas-MH Rater — Main Entry Point
Scans ./data/inbox/ for SERFF filings (PDF/XLSX)
and dispatches parsing + storage workflows.
"""

import os
import sys
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

SERFF_INBOX = os.getenv("SERFF_INBOX", "./data/inbox")
SUPPORTED_EXTENSIONS = {".pdf", ".xlsx", ".xls"}


def main():
    inbox = Path(SERFF_INBOX)
    inbox.mkdir(parents=True, exist_ok=True)

    files = [f for f in inbox.iterdir() if f.suffix.lower() in SUPPORTED_EXTENSIONS]

    if not files:
        logging.info("No new filings in inbox. Waiting for upload.")
        return

    logging.info(f"Found {len(files)} filing(s) to process: {[f.name for f in files]}")

    for filepath in files:
        logging.info(f"Processing: {filepath.name}")
        # [DEV] Placeholder — actual parsing dispatched per carrier model
        # TODO: Integrate carrier-specific parsers from models/


if __name__ == "__main__":
    main()