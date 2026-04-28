"""
[DEV] Tower Hill Prime Insurance Company (TOWERHILL) — Texas Manufactured Home Parser
Parses SERFF filing "TX MH 06-25 Rate & Rule Manual v1.pdf" into normalized rate tables.
Carrier ID: 4 (pre-seeded in schema/init.sql)

Key differences from AMERMOD:
  - No territory factors — uses Occupancy + Age of Home instead
  - Age of Home multiplier: 0-50 years for Dwelling/Other Structures/Personal Property
  - Deductible matrix: Dwelling Limit x All Other Peril Deductible x Wind/Hail Deductible -> Rate
  - Optional coverages with flat dollar fees and factor adjustments
"""

import re
import json
import logging
from pathlib import Path
import pymupdf

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


class TowerHillParser:
    CARRIER_CODE = "TOWERHILL"
    STATE = "TX"
    PRODUCT = "Manufactured Home"

    base_rates: dict = {}
    age_factors: dict = {}            # {coverage: {age: factor}}
    optional_coverages: dict = {}      # flat fee optional coverages
    optional_factors: dict = {}       # multiplicative factor optional coverages
    water_damage_reduced: dict = {}
    inspection_fee: float = 34.00
    inspection_fee_waiver: float = -34.00
    deductibles: list = []

    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self.doc = pymupdf.open(pdf_path)

    def parse(self) -> dict:
        logger.info(f"Parsing {self.pdf_path} — {len(self.doc)} pages")
        for page_num, page in enumerate(self.doc, start=1):
            text = page.get_text()
            desc = self._extract_table_description(text)

            if "Age of Home" in desc:
                self._parse_age_factors(text)
            elif "Base Rate" in desc:
                self._parse_base_rate(text)
            elif "Inspection Fee" in desc and "Waiver" not in desc:
                self._parse_inspection_fee(text)
            elif "Inspection Fee Waiver" in desc:
                self._parse_inspection_fee_waiver(text)
            elif "Water Damage Reduced Limit" in desc:
                self._parse_water_damage_reduced(text)
            elif "Roofing Materials Payment Schedule" in desc:
                self._parse_rmps(text)
            if "Deductible" in str(desc):
                logger.info(f"  -> desc={repr(desc)}, calling _parse_deductibles")
                self._parse_deductibles(text)

        return self.to_json()

    def _extract_table_description(self, text: str) -> str:
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        # Case 1: "Table Description: <value>" inline on same line
        match = re.search(r"Table Description[:]\s+(.+?)(?:\n|Page|$)", text, re.IGNORECASE)
        if match and match.group(1).strip() and not re.match(r"^Page\s+\d+$", match.group(1).strip()):
            desc = match.group(1).strip()
            # Skip dollar amounts — those are dwelling limit values, not descriptions
            if not re.match(r"^\$", desc):
                return desc
        # Case 2: "Table Description:" on its own line — scan next lines
        for i, line in enumerate(lines):
            if re.match(r"^Table Description[:]$", line, re.IGNORECASE):
                for j in range(i + 1, len(lines)):
                    val = lines[j]
                    if val in ["Deductible", "Dwelling Limit", "All Other Peril",
                               "Wind/Hail Deductible", "Rate"]:
                        continue
                    if re.match(r"^Page\s+\d+$", val):
                        continue
                    # Skip dollar amounts — those are dwelling limit values, not table descriptions
                    if re.match(r"^\$", val):
                        continue
                    return val.strip()
        # Case 3: No meaningful marker — detect page type by content signature
        has_deductible = "Deductible" in text and "Dwelling Limit" in text and "All Other Peril Deductible" in text
        if has_deductible:
            return "Deductible"
        if "Age of Home" in text and "Coverage" in text and "Factor" in text:
            return "Age of Home"
        if "Base Rate" in text and "Coverage" in text:
            return "Base Rate"
        return ""

    # ─── Age of Home Factors (pages 5-6) ───────────────────────────────────────
    def _parse_age_factors(self, text: str):
        """Each age/coverage block: Coverage | Age (number) | Factor (number) — separate lines."""
        logger.info("Parsing: Age of Home Factors")
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        current_coverage = None
        pending_age = None
        for line in lines:
            m_cov = re.match(r"^(Dwelling|Other Structures|Personal Property)$", line)
            if m_cov:
                cov = m_cov.group(1).lower().replace(" ", "_")
                if cov not in self.age_factors:
                    self.age_factors[cov] = {}
                current_coverage = cov
                pending_age = None
                continue
            m_age = re.match(r"^(\d+)$", line)
            if m_age and current_coverage:
                pending_age = int(m_age.group(1))
                continue
            m_factor = re.match(r"^([\d.]+)$", line)
            if m_factor and current_coverage and pending_age is not None:
                self.age_factors[current_coverage][pending_age] = float(m_factor.group(1))
                pending_age = None
                continue

    # ─── Base Rate (page 7) ───────────────────────────────────────────────────
    def _parse_base_rate(self, text: str):
        logger.info("Parsing: Base Rate")
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        in_optional = False
        for i, line in enumerate(lines):
            # Detect optional coverages block
            if "Optional Coverages" in line:
                in_optional = True
            # Parse coverage/occupancy base rate
            m_cov = re.match(r"^(Dwelling|Other Structures|Personal Property)$", line)
            if m_cov:
                if i + 1 < len(lines) and i + 2 < len(lines):
                    occ = lines[i + 1]
                    rate_match = re.search(r"[\d.]+", lines[i + 2])
                    if rate_match:
                        rate = float(rate_match.group())
                        self.base_rates[f"{m_cov.group(1)}|{occ}"] = rate
                continue
            # Flat-fee optional coverages (Animal Liability Exclusion, Identity Fraud Expense, etc.)
            if in_optional and not m_cov:
                if re.match(r"^(Animal Liability Exclusion|Identity Fraud Expense|Enhanced Coverage|"
                            r"Equipment Breakdown|Golf Cart Physical Damage and Liability Extension|"
                            r"Hobby Farming|Service Line|Trip Collision|Vacancy Permission)$", line):
                    if i + 1 < len(lines):
                        fee_match = re.search(r"-?\d+\.\d+", lines[i + 1])
                        if fee_match:
                            self.optional_coverages[line] = float(fee_match.group())
                # Factor-based optionals (Roof Exclusion)
                if "Roof Exclusion" in line and i + 1 < len(lines):
                    f_match = re.search(r"-?[\d.]+", lines[i + 1])
                    if f_match:
                        self.optional_factors["Roof Exclusion"] = float(f_match.group())

    # ─── Inspection Fee (page 8) ───────────────────────────────────────────────
    def _parse_inspection_fee(self, text: str):
        for line in text.split("\n"):
            m = re.search(r"\d+\.\d+", line)
            if m:
                self.inspection_fee = float(m.group())

    def _parse_inspection_fee_waiver(self, text: str):
        for line in text.split("\n"):
            m = re.search(r"-?\d+\.\d+", line)
            if m:
                self.inspection_fee_waiver = float(m.group())

    # ─── Water Damage Reduced Limit (page 10) ─────────────────────────────────
    def _parse_water_damage_reduced(self, text: str):
        logger.info("Parsing: Water Damage Reduced Limit")
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        for line in lines:
            parts = line.split()
            if len(parts) >= 2:
                m = re.search(r"-?[\d.]+", parts[-1])
                if m:
                    self.water_damage_reduced[parts[0]] = float(m.group())

    # ─── RMPS — Roofing Materials Payment Schedule (pages 11-17) ─────────────
    def _parse_rmps(self, text: str):
        """[Grandfathered?] | Age | RoofMaterial | DwellingFactor | OtherStructFactor | PersonalPropFactor"""
        logger.info("Parsing: Roofing Materials Payment Schedule")
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        if "rmps" not in self.age_factors:
            self.age_factors["rmps"] = []
        for line in lines:
            m = re.match(
                r"^(Yes|No)\s+(\d+)\s+(.+?)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)$",
                line,
            )
            if m:
                self.age_factors["rmps"].append({
                    "grandfathered": m.group(1) == "Yes",
                    "age": int(m.group(2)),
                    "roof_material": m.group(3).strip(),
                    "dwelling_factor": float(m.group(4)),
                    "other_structures_factor": float(m.group(5)),
                    "personal_property_factor": float(m.group(6)),
                })

    # ─── Deductibles (pages 18-24) ───────────────────────────────────────────
    def _parse_deductibles(self, text: str):
        """Lookback parser: for each standalone rate line, look back to find
        the nearest DL and AOP values. Lines with '%' or '(' are descriptions
        and are skipped. Values >= 5000 are DLs; values < 5000 are AOPs."""
        logger.info("Parsing: Deductibles")
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        skip_keys = ["Deductible", "Dwelling Limit", "All Other Peril",
                     "Wind/Hail Deductible", "Rate", "(>=)"]

        for i, line in enumerate(lines):
            if any(k in line for k in skip_keys):
                continue
            m_rate = re.match(r"^[\d.]+$", line)
            if not m_rate:
                continue

            rate_val = float(m_rate.group(0))
            dl_val = None
            aop_val = None

            # Look back up to 8 lines for DL and AOP candidates
            for j in range(i - 1, max(0, i - 8), -1):
                back = lines[j]
                # Skip description lines
                if "%" in back or "(" in back:
                    continue
                m_candidate = re.match(r"^\$(\d[\d,]*)", back)
                if not m_candidate:
                    continue
                val = int(m_candidate.group(1).replace(",", ""))
                # ≥ 5000 → dwelling limit; < 5000 → AOP deductible
                if val >= 5000:
                    if dl_val is None:
                        dl_val = val
                else:
                    if aop_val is None:
                        aop_val = val

            if dl_val is not None and aop_val is not None:
                self.deductibles.append({
                    "dwelling_limit": dl_val,
                    "all_other_peril_deductible": aop_val,
                    "rate": rate_val,
                })
                dl_val = None
                aop_val = None

    def to_json(self) -> dict:
        return {
            "carrier_code": self.CARRIER_CODE,
            "state": self.STATE,
            "product": self.PRODUCT,
            "base_rates": self.base_rates,
            "age_factors": self.age_factors,
            "optional_coverages": self.optional_coverages,
            "optional_factors": self.optional_factors,
            "water_damage_reduced": self.water_damage_reduced,
            "inspection_fee": self.inspection_fee,
            "inspection_fee_waiver": self.inspection_fee_waiver,
            "deductibles": self.deductibles,
        }

    def save_json(self, output_path: str):
        data = self.parse()
        with open(output_path, "w") as f:
            json.dump(data, f, indent=2)
        logger.info(f"Saved parsed rate data to {output_path}")
        return data