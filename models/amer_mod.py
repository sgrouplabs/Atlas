"""
[DEV] American Modern (AMERMOD) — Texas Manufactured Home Parser
Parses SERFF filing TX071MH-A into normalized rate tables.
Carrier ID: 2 (pre-seeded in schema/init.sql)
"""

import re
import json
import logging
from pathlib import Path
from typing import Optional
import pymupdf

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


class AmerModParser:
    CARRIER_CODE = "AMERMOD"
    STATE = "TX"
    PRODUCT = "Manufactured Home"

    # Rate table storage
    base_rates: dict = {}
    territory_factors: dict = {}
    flood_territory_factors: dict = {}
    deductible_wsh_excluded: list = []
    deductible_wsh_included: list = []
    scaling_factors: dict = {}
    inspection_fee: float = 26.00
    flood_min_premium: float = 50.00

    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self.doc = pymupdf.open(pdf_path)

    def parse(self) -> dict:
        """Full parse of all rate tables."""
        logger.info(f"Parsing {self.pdf_path} — {len(self.doc)} pages")

        for page_num, page in enumerate(self.doc, start=1):
            text = page.get_text()
            table_desc = self._extract_table_description(text)

            if "Base Rate" in table_desc:
                self._parse_base_rate(text)
            elif "Dwelling Scaling Factor" in table_desc:
                self._parse_scaling_factor(text, "dwelling")
            elif "Flood Minimum Premium" in table_desc:
                self._parse_flood_min_premium(text)
            elif "Flood Territory" in table_desc and "Secondary" not in table_desc:
                self._parse_flood_territory(text)
            elif "Inspection Fee" in table_desc and "Waiver" not in table_desc:
                self._parse_inspection_fee(text)
            elif "Inspection Fee Waiver" in table_desc:
                self._parse_inspection_fee_waiver(text)
            elif "Other Structures Scaling Factor" in table_desc:
                self._parse_scaling_factor(text, "other_structures")
            elif "Personal Property Scaling Factor" in table_desc:
                self._parse_scaling_factor(text, "personal_property")
            elif "Territory" in table_desc and "Map" not in table_desc and "Flood" not in table_desc:
                self._parse_territory(text)
            elif "Water Damage Reduced Limit" in table_desc:
                self._parse_water_damage_reduced(text)
            elif "Deductible" in table_desc and "Excluded" in table_desc:
                self._parse_deductible_wsh_excluded(text)
            elif "Deductible" in table_desc and "Included" in table_desc:
                self._parse_deductible_wsh_included(text)

        return self.to_json()

    def _extract_table_description(self, text: str) -> str:
        """Extract the Table Description from page text."""
        match = re.search(r"Table Description[:]?\s*(.+?)(?:\n|Page)", text, re.IGNORECASE)
        return match.group(1).strip() if match else ""

    def _parse_base_rate(self, text: str):
        """Page 7 — Base Rate table. Multiple blocks of occupancy/rate pairs."""
        logger.info("Parsing: Base Rate")
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        for i, line in enumerate(lines):
            if re.match(r"^(Owner|Seasonal|Owner/Seasonal|Owner/Seasonal/Rental)$", line):
                if i + 1 < len(lines):
                    # Strip commas from numbers like "1,305.0000"
                    rate_str = re.sub(r"[^\d.]", "", lines[i + 1])
                    if rate_str:
                        occupancy = line
                        rate = float(rate_str)
                        self.base_rates[occupancy] = rate

    def _parse_scaling_factor(self, text: str, factor_type: str):
        """Pages 8, 13, 14 — Scaling factors for dwelling/other structures/personal property."""
        logger.info(f"Parsing: Scaling Factor — {factor_type}")
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        key = f"scaling_{factor_type}"
        self.scaling_factors[key] = {}
        for i, line in enumerate(lines):
            if "Water Damage" in line and i + 2 < len(lines):
                option = line.replace("Water Damage", "").strip()
                rate_line = lines[i + 2]
                rate_match = re.search(r"[\d.]+", rate_line)
                if rate_match:
                    self.scaling_factors[key][option] = float(rate_match.group())

    def _parse_flood_min_premium(self, text: str):
        """Page 9 — Flood Minimum Premium."""
        logger.info("Parsing: Flood Minimum Premium")
        for line in text.split("\n"):
            m = re.search(r"(\d+\.\d+)", line)
            if m and "Flood" in text:
                self.flood_min_premium = float(m.group(1))

    def _parse_flood_territory(self, text: str):
        """Page 10 — Flood Territory factors."""
        logger.info("Parsing: Flood Territory")
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        for line in lines:
            m = re.match(r"Flood\s+(\d+)\s+([\d.]+)", line)
            if m:
                self.flood_territory_factors[int(m.group(1))] = float(m.group(2))

    def _parse_inspection_fee(self, text: str):
        """Page 11 — Inspection Fee."""
        for line in text.split("\n"):
            m = re.search(r"\d+\.\d+", line)
            if m:
                self.inspection_fee = float(m.group())

    def _parse_inspection_fee_waiver(self, text: str):
        """Page 12 — Inspection Fee Waiver."""
        for line in text.split("\n"):
            m = re.search(r"-?\d+\.\d+", line)
            if m:
                # Store as negative for waiver
                pass

    def _parse_territory(self, text: str):
        """Pages 15-16 — Territory factors (Dwelling + Other Structures + Personal Property)."""
        logger.info("Parsing: Territory Factors")
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        # Determine which coverage type based on what appears in text first
        coverage_keys = ["dwelling", "other_structures", "personal_property"]
        for cov_key in coverage_keys:
            self.territory_factors[cov_key] = {}

        current_coverage = None
        for line in lines:
            m_cov = re.match(r"^(Dwelling|Other Structures|Personal Property)$", line)
            if m_cov:
                current_coverage = m_cov.group(1).lower().replace(" ", "_")
                continue
            m = re.match(r"^(\d+)\s+([\d.]+)$", line)
            if m and current_coverage:
                terr = int(m.group(1))
                factor = float(m.group(2))
                if current_coverage in self.territory_factors:
                    self.territory_factors[current_coverage][terr] = factor

    def _parse_water_damage_reduced(self, text: str):
        """Page 17 — Water Damage Reduced Limit."""
        logger.info("Parsing: Water Damage Reduced Limit")
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        self.scaling_factors["water_damage_reduced"] = {}
        for line in lines:
            m = re.match(r"(\d+%?)\s+(-?[\d.]+)", line)
            if m:
                self.scaling_factors["water_damage_reduced"][m.group(1)] = float(m.group(2))

    def _parse_deductible_wsh_excluded(self, text: str):
        """Pages 18-21 — Deductible Windstorm/Hail Excluded."""
        logger.info("Parsing: Deductible WSH Excluded")
        self._parse_deductible_table(text, "deductible_wsh_excluded")

    def _parse_deductible_wsh_included(self, text: str):
        """Pages 22-33 — Deductible Windstorm/Hail Included."""
        logger.info("Parsing: Deductible WSH Included")
        self._parse_deductible_table(text, "deductible_wsh_included")

    def _parse_deductible_table(self, text: str, storage_key: str):
        if not hasattr(self, storage_key):
            setattr(self, storage_key, [])
        records = getattr(self, storage_key)
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        i = 0
        while i < len(lines):
            # Look for territory number followed by coverage type
            if re.match(r"^\d+$", lines[i]):
                territory = int(lines[i])
                if i + 2 < len(lines) and re.match(r"^(Dwelling|Other Structures|Personal Property)$", lines[i + 1]):
                    coverage = lines[i + 1].lower().replace(" ", "_")
                    if i + 3 < len(lines) and re.match(r"^(Owner/Seasonal|Owner/Seasonal/Rental|Seasonal)$", lines[i + 2]):
                        occupancy = lines[i + 2]
                        # Find the rate — it should be the last numeric field after dwelling limit amounts
                        # Scan forward for rate (a float that appears after dollar amounts)
                        j = i + 3
                        while j < len(lines):
                            rate_match = re.match(r"^([\d.]+)$", lines[j])
                            if rate_match:
                                rate = float(rate_match.group(1))
                                records.append({
                                    "territory": territory,
                                    "coverage": coverage,
                                    "occupancy": occupancy,
                                    "rate": rate,
                                })
                                break
                            j += 1
            i += 1

    def to_json(self) -> dict:
        """Export all parsed rate data as JSON."""
        return {
            "carrier_code": self.CARRIER_CODE,
            "state": self.STATE,
            "product": self.PRODUCT,
            "base_rates": self.base_rates,
            "territory_factors": self.territory_factors,
            "flood_territory_factors": self.flood_territory_factors,
            "deductible_wsh_excluded": self.deductible_wsh_excluded,
            "deductible_wsh_included": self.deductible_wsh_included,
            "scaling_factors": self.scaling_factors,
            "inspection_fee": self.inspection_fee,
            "flood_min_premium": self.flood_min_premium,
        }

    def save_json(self, output_path: str):
        data = self.parse()
        with open(output_path, "w") as f:
            json.dump(data, f, indent=2)
        logger.info(f"Saved parsed rate data to {output_path}")
        return data