"""
src/csv_utils.py - CSV parsing utilities for match upload.
"""

import csv
import io
from datetime import datetime
from typing import List, Dict, Tuple
import logging

logger = logging.getLogger("esports-bot.csv_utils")


def parse_match_csv(
    csv_content: str,
) -> Tuple[List[Dict], List[str]]:
    """
    Parse CSV content for match upload.

    Expected CSV format:
    scheduled_time,team1,team2[,external_id]

    scheduled_time should be in ISO 8601 format (e.g., 2025-01-15T14:00:00Z)

    Returns:
        Tuple of (valid_rows, errors) where:
        - valid_rows: List of dicts with keys: scheduled_time, team1, team2,
          external_id (optional)
        - errors: List of error messages for invalid rows
    """
    valid_rows = []
    errors = []

    try:
        reader = csv.DictReader(io.StringIO(csv_content))

        # Check required headers
        if reader.fieldnames is None:
            errors.append("CSV file is empty or has no header row")
            return valid_rows, errors

        required_headers = {"scheduled_time", "team1", "team2"}
        optional_headers = {"external_id"}
        all_valid_headers = required_headers | optional_headers

        actual_headers = set(reader.fieldnames)

        if not required_headers.issubset(actual_headers):
            missing = required_headers - actual_headers
            errors.append(
                f"CSV missing required headers: {', '.join(missing)}"
            )
            return valid_rows, errors

        # Warn about unexpected headers
        unexpected = actual_headers - all_valid_headers
        if unexpected:
            logger.warning(
                "CSV contains unexpected headers: %s",
                ", ".join(unexpected)
            )

        for row_num, row in enumerate(reader, start=2):  # start=2 (header=1)
            row_errors = []

            # Validate required fields
            scheduled_time_str = row.get("scheduled_time", "").strip()
            team1 = row.get("team1", "").strip()
            team2 = row.get("team2", "").strip()

            if not scheduled_time_str:
                row_errors.append("scheduled_time is empty")
            if not team1:
                row_errors.append("team1 is empty")
            if not team2:
                row_errors.append("team2 is empty")

            # Parse datetime
            scheduled_time = None
            if scheduled_time_str:
                try:
                    scheduled_time = datetime.fromisoformat(
                        scheduled_time_str.replace("Z", "+00:00")
                    )
                except ValueError:
                    row_errors.append(
                        f"Invalid datetime format: '{scheduled_time_str}' "
                        "(expected ISO 8601, e.g., 2025-01-15T14:00:00Z)"
                    )

            if row_errors:
                errors.append(
                    f"Row {row_num}: " + "; ".join(row_errors)
                )
                continue

            # Valid row
            match_data = {
                "scheduled_time": scheduled_time,
                "team1": team1,
                "team2": team2,
            }

            # Include optional external_id if present
            external_id = row.get("external_id", "").strip()
            if external_id:
                match_data["external_id"] = external_id

            valid_rows.append(match_data)

    except csv.Error as e:
        errors.append(f"CSV parsing error: {e}")
    except Exception as e:
        logger.exception("Unexpected error parsing CSV")
        errors.append(f"Unexpected error: {e}")

    return valid_rows, errors
