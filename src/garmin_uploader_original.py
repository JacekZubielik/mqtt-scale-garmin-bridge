"""Upload body composition to Garmin Connect."""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from garminconnect import Garmin

logger = logging.getLogger(__name__)


class GarminUploader:
    """Upload body composition to Garmin Connect."""

    def __init__(self, tokens_path: str):
        self.tokens_path = Path(tokens_path)
        self.garmin: Optional[Garmin] = None
        self.current_email: Optional[str] = None

    def login(self, email: str) -> bool:
        """
        Login to Garmin Connect using saved token.

        Token must be generated first by import_tokens.py
        """
        # Skip if already logged in as this user
        if self.garmin and self.current_email == email:
            return True

        token_file = self.tokens_path / email

        if not token_file.exists():
            logger.error(f"Token file not found: {token_file}")
            logger.error("Run tools/import_tokens.py first to generate tokens")
            return False

        try:
            tokenstore = token_file.read_text()
            self.garmin = Garmin()
            self.garmin.login(tokenstore)
            self.current_email = email
            logger.info(f"Logged in to Garmin Connect as {email}")
            return True
        except Exception as e:
            logger.error(f"Failed to login to Garmin: {e}")
            self.garmin = None
            self.current_email = None
            return False

    def upload_body_composition(self, timestamp: datetime, metrics: dict) -> bool:
        """
        Upload body composition to Garmin Connect.

        Args:
            timestamp: Measurement time
            metrics: Metrics dict from calculate_body_composition()
        """
        if not self.garmin:
            logger.error("Not logged in to Garmin")
            return False

        try:
            self.garmin.add_body_composition(
                timestamp=timestamp.isoformat(),
                weight=metrics["weight"],
                bmi=metrics["bmi"],
                percent_fat=metrics["percent_fat"],
                muscle_mass=metrics["muscle_mass"],
                bone_mass=metrics["bone_mass"],
                percent_hydration=metrics["percent_hydration"],
                physique_rating=metrics["physique_rating"],
                visceral_fat_rating=metrics["visceral_fat_rating"],
                metabolic_age=metrics["metabolic_age"],
                basal_met=metrics["basal_met"],
            )
            logger.info(
                f"Uploaded to Garmin: {metrics['weight']}kg, {metrics['percent_fat']:.1f}% fat"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to upload to Garmin: {e}")
            return False
