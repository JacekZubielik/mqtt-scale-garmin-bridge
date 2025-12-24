"""Filter duplicate measurements from scale."""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from .mqtt_subscriber import ScaleMeasurement

logger = logging.getLogger(__name__)


@dataclass
class FilteredMeasurement:
    """Filtered, final measurement."""

    timestamp: datetime
    weight_kg: float
    impedance: int
    mac_address: str


class MeasurementFilter:
    """
    Filter repeated measurements from scale.

    Xiaomi scale sends data every ~2 seconds during measurement.
    This filter:
    1. Waits for measurement with impedance (indicates stable measurement)
    2. Ignores duplicates for a specified time
    3. Groups measurements from the same "weighing session"
    """

    def __init__(self, cooldown_seconds: int = 30, require_impedance: bool = True):
        """
        Args:
            cooldown_seconds: Minimum time between accepted measurements
            require_impedance: Whether to require impedance (True for body composition)
        """
        self.cooldown = timedelta(seconds=cooldown_seconds)
        self.require_impedance = require_impedance
        self.last_measurement: Optional[datetime] = None
        self.last_weight: Optional[float] = None

    def process(self, measurement: ScaleMeasurement) -> Optional[FilteredMeasurement]:
        """
        Process measurement and return FilteredMeasurement if it should be saved.

        Returns:
            FilteredMeasurement if measurement is valid, None if duplicate
        """
        # Check if we have impedance (if required)
        if self.require_impedance and not measurement.has_impedance:
            logger.debug(f"Skipping measurement without impedance: {measurement.weight_kg}kg")
            return None

        now = datetime.now()

        # Check cooldown
        if self.last_measurement:
            elapsed = now - self.last_measurement
            if elapsed < self.cooldown:
                # In cooldown period - check if it's the same measurement
                if self.last_weight and abs(measurement.weight_kg - self.last_weight) < 0.1:
                    logger.debug(f"Duplicate measurement filtered: {measurement.weight_kg}kg")
                    return None

        # Accept measurement
        self.last_measurement = now
        self.last_weight = measurement.weight_kg

        logger.info(
            f"Accepted measurement: {measurement.weight_kg}kg, impedance={measurement.impedance}"
        )

        return FilteredMeasurement(
            timestamp=now,
            weight_kg=measurement.weight_kg,
            impedance=measurement.impedance,
            mac_address=measurement.mac_address,
        )
