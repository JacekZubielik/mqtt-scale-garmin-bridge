"""Body metrics calculation module."""

from .calculator import bodyMetrics
from .scales import bodyScales


def calculate_body_composition(
    weight_kg: float,
    impedance: int,
    height_cm: int,
    age: int,
    sex: str,  # 'male' or 'female'
) -> dict:
    """
    Calculate full body composition based on weight and impedance.

    Args:
        weight_kg: Weight in kilograms
        impedance: Impedance in ohms (from scale)
        height_cm: Height in centimeters
        age: Age in years
        sex: 'male' or 'female'

    Returns:
        dict with keys: bmi, percent_fat, muscle_mass, bone_mass,
                        percent_hydration, visceral_fat, metabolic_age,
                        basal_met, physique_rating, ideal_weight
    """
    lib = bodyMetrics(weight_kg, height_cm, age, sex, impedance)

    return {
        "weight": weight_kg,
        "bmi": lib.getBMI(),
        "percent_fat": lib.getFatPercentage(),
        "muscle_mass": lib.getMuscleMass(),
        "bone_mass": lib.getBoneMass(),
        "percent_hydration": lib.getWaterPercentage(),
        "visceral_fat_rating": lib.getVisceralFat(),
        "metabolic_age": lib.getMetabolicAge(),
        "basal_met": lib.getBMR(),
        "physique_rating": lib.getBodyType(),
        "ideal_weight": lib.getIdealWeight(),
        "protein": lib.getProteinPercentage(),
        "lean_body_mass": lib.getLBMCoefficient(),
    }


__all__ = ["bodyMetrics", "bodyScales", "calculate_body_composition"]
