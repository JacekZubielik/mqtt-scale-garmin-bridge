"""Upload body composition to Garmin Connect using garth library."""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import garth
from garth.exc import GarthException

logger = logging.getLogger(__name__)


class GarminUploader:
    """Upload body composition to Garmin Connect using garth."""

    def __init__(self, garth_token_path: str):
        """Initialize with garth token directory."""
        self.garth_token_path = garth_token_path
        self.authenticated = False
        self._init_garth()

    def _init_garth(self):
        """Initialize garth session from saved tokens."""
        try:
            garth.resume(self.garth_token_path)
            self.authenticated = True
            logger.info(f"Garth session resumed for: {garth.client.username}")
        except GarthException as e:
            logger.error(f"Failed to resume garth session: {e}")
            logger.error("Token may be expired or invalid")
            self.authenticated = False
        except Exception as e:
            logger.error(f"Unexpected error initializing garth: {e}")
            self.authenticated = False

    def login(self, email: str) -> bool:
        """
        Check authentication status.

        For garth, authentication is handled in __init__ via resume().
        This method maintains API compatibility with existing code.
        """
        if not self.authenticated:
            logger.error("Garth not authenticated")
            return False

        try:
            # Verify current session is working
            username = garth.client.username
            if username != email:
                logger.warning(f"Expected {email}, but authenticated as {username}")

            logger.info(f"Garth authenticated as: {username}")
            return True

        except Exception as e:
            logger.error(f"Authentication check failed: {e}")
            return False

    def upload_body_composition(self, timestamp: datetime, metrics: dict) -> bool:
        """
        Upload body composition to Garmin Connect using garth.

        Args:
            timestamp: Measurement time
            metrics: Metrics dict from calculate_body_composition()
        """
        if not self.authenticated:
            logger.error("Not authenticated with Garmin")
            return False

        try:
            # Prepare payload for Garmin Connect API
            payload = {
                "weight": int(metrics["weight"] * 1000),  # Convert kg to grams
                "unitKey": "kg",
                "timestampGMT": int(timestamp.timestamp() * 1000),  # Unix timestamp in ms
            }

            # Add body composition data if available
            if "bmi" in metrics:
                payload["bmi"] = round(metrics["bmi"], 2)

            if "percent_fat" in metrics:
                payload["bodyFatPercentage"] = round(metrics["percent_fat"], 1)

            if "percent_hydration" in metrics:
                payload["bodyWater"] = round(metrics["percent_hydration"], 1)

            if "bone_mass" in metrics:
                payload["boneMass"] = int(metrics["bone_mass"] * 1000)  # Convert kg to grams

            if "muscle_mass" in metrics:
                payload["muscleMass"] = int(metrics["muscle_mass"] * 1000)  # Convert kg to grams

            if "visceral_fat_rating" in metrics:
                payload["visceralFat"] = int(metrics["visceral_fat_rating"])

            if "metabolic_age" in metrics:
                payload["metabolicAge"] = int(metrics["metabolic_age"])

            # Upload via garth connectapi
            response = garth.connectapi("/weight-service/user-weight", method="POST", json=payload)

            logger.info(
                f"Uploaded to Garmin Connect: {metrics['weight']:.1f}kg, "
                f"{metrics.get('percent_fat', 0):.1f}% fat"
            )
            logger.debug(f"Garmin API response: {response}")

            return True

        except GarthException as e:
            logger.error(f"Garth API error: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to upload to Garmin: {e}")
            return False

    def test_connection(self) -> bool:
        """Test connection to Garmin Connect."""
        if not self.authenticated:
            return False

        try:
            # Simple API call to test connectivity
            profile = garth.UserProfile.get()
            logger.info(f"Connection test successful: {profile.display_name}")
            return True
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False
