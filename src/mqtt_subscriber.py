"""MQTT Subscriber for Xiaomi Scale data via OpenMQTTGateway."""

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Optional, Tuple

import paho.mqtt.client as mqtt

from .body_metrics import calculate_body_composition

logger = logging.getLogger(__name__)


@dataclass
class ScaleMeasurement:
    """Measurement from Xiaomi Scale via OpenMQTTGateway."""

    timestamp: datetime
    mac_address: str
    weight: float
    unit: str
    impedance: Optional[int]
    weighing_mode: str
    model_id: str
    rssi: int
    # Body composition metrics (calculated if impedance available)
    body_metrics: Optional[dict] = None

    @property
    def weight_kg(self) -> float:
        """Return weight in kg regardless of unit."""
        if self.unit == "kg":
            return self.weight
        elif self.unit == "lb":
            return self.weight * 0.453592
        elif self.unit == "jin":
            return self.weight * 0.5
        return self.weight

    @property
    def has_impedance(self) -> bool:
        """Check if measurement has impedance (required for body composition)."""
        return self.impedance is not None and self.impedance > 0


class MqttSubscriber:
    """MQTT subscriber for scale measurements."""

    def __init__(
        self,
        host: str,
        port: int = 1883,
        username: Optional[str] = None,
        password: Optional[str] = None,
        user_height: int = 172,
        user_age: int = 40,
        user_sex: str = "male",
    ):
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        if username and password:
            self.client.username_pw_set(username, password)
        self.client.on_message = self._on_message
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.host = host
        self.port = port
        self.topic: Optional[str] = None
        self.callback: Optional[Callable[[ScaleMeasurement], None]] = None
        self.user_height = user_height
        self.user_age = user_age
        self.user_sex = user_sex
        # Duplicate filtering
        self.last_measurement: Optional[Tuple] = None

    def subscribe(self, topic: str, callback: Callable[[ScaleMeasurement], None]):
        """
        Subscribe to topic and call callback on each measurement.

        Args:
            topic: MQTT topic, e.g. "home/OMG_ESP32_BLE/BTtoMQTT/+"
            callback: Function called with ScaleMeasurement
        """
        self.topic = topic
        self.callback = callback

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        logger.info(f"Connected to MQTT broker: {reason_code}")
        if self.topic:
            client.subscribe(self.topic)
            logger.info(f"Subscribed to: {self.topic}")

    def _on_disconnect(self, client, userdata, flags, reason_code, properties):
        logger.warning(f"Disconnected from MQTT broker: {reason_code}")

    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode("utf-8"))

            # Check if it's a Xiaomi scale
            model_id = payload.get("model_id", "")
            if not model_id or "XMTZC" not in model_id:
                return  # Ignore other devices

            # Check if it's a person measurement (not object)
            if payload.get("weighing_mode") != "person":
                logger.debug(
                    f"Ignoring non-person measurement: {payload.get('weighing_mode')}"
                )
                return

            weight = payload.get("weight")
            impedance = payload.get("impedance")

            # Require both weight and impedance for body composition
            if not weight or not impedance:
                logger.debug("Ignoring measurement without weight or impedance")
                return

            # Calculate body composition
            body_metrics = calculate_body_composition(
                weight_kg=weight,
                impedance=impedance,
                height_cm=self.user_height,
                age=self.user_age,
                sex=self.user_sex,
            )

            # Check for duplicate measurement (compare all metrics)
            current_measurement = (
                weight,
                impedance,
                body_metrics["bmi"],
                body_metrics["percent_fat"],
                body_metrics["muscle_mass"],
                body_metrics["bone_mass"],
                body_metrics["percent_hydration"],
                body_metrics["visceral_fat_rating"],
                body_metrics["metabolic_age"],
            )

            if self.last_measurement == current_measurement:
                logger.debug("Skipping duplicate measurement")
                return  # Skip duplicate

            self.last_measurement = current_measurement

            measurement = ScaleMeasurement(
                timestamp=datetime.now(),
                mac_address=payload.get("id", ""),
                weight=weight,
                unit=payload.get("unit", "kg"),
                impedance=impedance,
                weighing_mode=payload.get("weighing_mode", ""),
                model_id=model_id,
                rssi=payload.get("rssi", 0),
                body_metrics=body_metrics,
            )

            # Log detailed body composition
            logger.info("=== NEW MEASUREMENT ===")
            logger.info(f"Weight: {weight} kg")
            logger.info(f"Impedance: {impedance} ohm")
            logger.info("")
            logger.info("=== BODY COMPOSITION ===")
            logger.info(f"BMI: {body_metrics['bmi']:.1f}")
            logger.info(f"Fat: {body_metrics['percent_fat']:.1f}%")
            logger.info(f"Muscle: {body_metrics['muscle_mass']:.1f} kg")
            logger.info(f"Bone: {body_metrics['bone_mass']:.1f} kg")
            logger.info(f"Water: {body_metrics['percent_hydration']:.1f}%")
            logger.info(f"Visceral: {body_metrics['visceral_fat_rating']:.1f}")
            logger.info(f"Metabolic age: {body_metrics['metabolic_age']:.0f}")
            logger.info("========================")

            if self.callback:
                self.callback(measurement)

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON: {e}")
        except Exception as e:
            logger.error(f"Error processing message: {e}")

    def run(self):
        """Run MQTT daemon (blocking)."""
        try:
            logger.info(f"Connecting to MQTT broker: {self.host}:{self.port}")
            self.client.connect(self.host, self.port, keepalive=60)
            logger.info("Connected to MQTT broker successfully")
            logger.info(f"Starting MQTT loop for {self.host}:{self.port}")
            self.client.loop_forever()
        except ConnectionRefusedError:
            logger.error(f"❌ MQTT Broker connection refused: {self.host}:{self.port}")
            logger.error("Please check:")
            logger.error("  1. MQTT broker is running")
            logger.error("  2. Network connectivity to broker")
            logger.error("  3. Firewall settings")
            logger.error("  4. Broker address in config.yaml")
            logger.error("Application will exit gracefully.")
            return
        except Exception as e:
            logger.error(f"❌ MQTT connection error: {e}")
            logger.error(f"Failed to connect to MQTT broker at {self.host}:{self.port}")
            logger.error("Application will exit gracefully.")
            return

    def stop(self):
        """Stop daemon."""
        self.client.disconnect()
