"""
[DEV] Atlas-MH Rater — Main Entry Point
Scans ./data/inbox/ for SERFF filings (PDF/XLSX)
and dispatches carrier-specific parsers.
"""

import os
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

SERFF_INBOX = os.getenv("SERFF_INBOX", "./data/inbox")
SUPPORTED_EXTENSIONS = {".pdf", ".xlsx", ".xls"}
PARSED_OUTPUT = "./data/parsed"


def dispatch_parser(filepath: Path):
    """Route filing to the correct carrier parser."""
    filename = filepath.name.upper()

    if "TOWERHILL" in filename or "TOWER HILL" in filename or "TX MH 06-25" in filename:
        from models.tower_hill import TowerHillParser
        parser = TowerHillParser(str(filepath))
        return parser.save_json(f"{PARSED_OUTPUT}/{filepath.stem}_parsed.json")

    if "AMERMOD" in filename or "AMERICAN MODERN" in filename or "TX071MH" in filename:
        from models.amer_mod import AmerModParser
        parser = AmerModParser(str(filepath))
        return parser.save_json(f"{PARSED_OUTPUT}/{filepath.stem}_parsed.json")

    logger.warning(f"No parser registered for: {filepath.name}")
    return None


def main():
    inbox = Path(SERFF_INBOX)
    parsed = Path(PARSED_OUTPUT)
    inbox.mkdir(parents=True, exist_ok=True)
    parsed.mkdir(parents=True, exist_ok=True)

    files = [f for f in inbox.iterdir() if f.suffix.lower() in SUPPORTED_EXTENSIONS]

    if not files:
        logger.info("No new filings in inbox. Waiting for upload.")
        return

    for filepath in files:
        logger.info(f"Processing: {filepath.name}")
        try:
            result = dispatch_parser(filepath)
            if result:
                logger.info(f"Successfully parsed: {filepath.name}")
                logger.info(
                    f"Carrier: {result.get('carrier_code')} | State: {result.get('state')} | "
                    f"BaseRates: {len(result.get('base_rates', {}))} | "
                    f"TerritoryFactors: {len(result.get('territory_factors', {}))} | "
                    f"Deductible WSH Excl: {len(result.get('deductible_wsh_excluded', []))} | "
                    f"Deductible WSH Incl: {len(result.get('deductible_wsh_included', []))}"
                )
        except Exception as e:
            logger.error(f"Failed to process {filepath.name}: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    main()