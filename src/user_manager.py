"""User management and matching by weight."""

import logging
from dataclasses import dataclass
from datetime import date, datetime
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class User:
    """Scale user."""

    sex: str  # 'male' or 'female'
    height: int  # cm
    birthdate: str  # DD-MM-YYYY
    email: str  # Garmin Connect email
    max_weight: float  # kg
    min_weight: float  # kg

    @property
    def age(self) -> int:
        """Calculate age from birthdate."""
        today = date.today()
        birth = datetime.strptime(self.birthdate, "%d-%m-%Y")
        age = today.year - birth.year
        if (today.month, today.day) < (birth.month, birth.day):
            age -= 1
        return age


class UserManager:
    """Manage users and match measurements to users."""

    def __init__(self, users: List[User]):
        self.users = users
        logger.info(f"Loaded {len(users)} users")
        for user in users:
            logger.debug(
                f"  - {user.email}: {user.min_weight}-{user.max_weight}kg, {user.height}cm, {user.age}y"
            )

    def find_user_by_weight(self, weight_kg: float) -> Optional[User]:
        """
        Find user by weight.

        Assumes user weight ranges don't overlap.
        """
        for user in self.users:
            if user.min_weight <= weight_kg <= user.max_weight:
                logger.info(f"Matched user {user.email} for weight {weight_kg}kg")
                return user

        logger.warning(f"No user found for weight {weight_kg}kg")
        return None
