"""CSV backup for measurements."""

import csv
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class BackupManager:
    """Save measurements to CSV as backup."""

    def __init__(self, backup_path: str):
        self.backup_path = Path(backup_path)
        self.backup_path.mkdir(parents=True, exist_ok=True)

    def save(self, email: str, timestamp: datetime, metrics: dict):
        """Save measurement to CSV."""
        filename = self.backup_path / f"{email}.csv"
        file_exists = filename.exists()

        fieldnames = [
            "timestamp",
            "weight",
            "bmi",
            "percent_fat",
            "muscle_mass",
            "bone_mass",
            "percent_hydration",
            "visceral_fat_rating",
            "metabolic_age",
            "basal_met",
            "physique_rating",
            "protein",
            "lean_body_mass",
            "ideal_weight",
        ]

        with open(filename, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)

            if not file_exists:
                writer.writeheader()

            row = {"timestamp": timestamp.isoformat()}
            for key in fieldnames:
                if key != "timestamp" and key in metrics:
                    row[key] = metrics[key]

            writer.writerow(row)

        logger.debug(f"Saved backup to {filename}")
