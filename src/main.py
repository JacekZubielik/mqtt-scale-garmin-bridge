"""Main application - MQTT Scale to Garmin Bridge."""

import argparse
import logging
import signal
import sys
from pathlib import Path
from typing import Any, Optional, Type

import yaml

try:
    from .backup import BackupManager as BackupManagerClass

    BackupManager: Optional[Type[BackupManagerClass]] = BackupManagerClass
except ImportError:
    BackupManager = None

from .bridge_configurator import BridgeConfigurator

try:
    from .garmin_uploader import GarminUploader as GarminUploaderClass

    GarminUploader: Optional[Type[GarminUploaderClass]] = GarminUploaderClass
except ImportError:
    GarminUploader = None

from .mqtt_subscriber import MqttSubscriber, ScaleMeasurement
from .user_manager import User, UserManager

logger = logging.getLogger(__name__)


class MqttScaleGarminBridge:
    """Main application - bridge between MQTT and Garmin Connect."""

    def __init__(self, config_path: str):
        self.config = self._load_config(config_path)
        self._setup_logging()

        # Get user info for body composition calculation (use first user for now)
        first_user = self.config["users"][0] if self.config["users"] else {}
        user_height = first_user.get("height", 172)
        user_age = 40  # TODO: Calculate from birthdate
        user_sex = first_user.get("sex", "male")

        # Initialize components
        self.mqtt = MqttSubscriber(
            host=self.config["mqtt"]["host"],
            port=self.config["mqtt"].get("port", 1883),
            username=self.config["mqtt"].get("username"),
            password=self.config["mqtt"].get("password"),
            user_height=user_height,
            user_age=user_age,
            user_sex=user_sex,
        )

        self.users = UserManager([User(**u) for u in self.config["users"]])

        # Initialize Garmin uploader only if enabled
        self.garmin = None
        if (
            self.config.get("garmin", {}).get("enabled", True)
            and GarminUploader is not None
        ):
            self.garmin = GarminUploader(
                tokens_path=self.config["garmin"]["tokens_path"]
            )
        elif GarminUploader is None:
            logger.info("Garmin uploader not available (module not found)")

        # Initialize backup only if enabled
        self.backup = None
        if (
            self.config.get("backup", {}).get("enabled", False)
            and BackupManager is not None
        ):
            self.backup = BackupManager(backup_path=self.config["backup"]["path"])
        elif BackupManager is None:
            logger.info("Backup manager not available (module not found)")

        # Bridge configurator
        self.bridge_configurator = BridgeConfigurator(
            host=self.config["mqtt"]["host"],
            port=self.config["mqtt"].get("port", 1883),
        )

    def _load_config(self, path: str) -> dict[str, Any]:
        with open(path, "r") as f:
            config: dict[str, Any] = yaml.safe_load(f)
            return config

    def _setup_logging(self):
        log_config = self.config.get("logging", {})
        level = getattr(logging, log_config.get("level", "INFO").upper())
        log_format = log_config.get(
            "format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

        # Create logs directory if needed
        log_file = log_config.get("file")
        if log_file:
            import os

            log_dir = os.path.dirname(log_file)
            if log_dir and not os.path.exists(log_dir):
                os.makedirs(log_dir)

        handlers: list[logging.Handler] = []
        handlers.append(logging.StreamHandler())  # Console logging

        # Add file handler if configured
        if log_file:
            handlers.append(logging.FileHandler(log_file))

        logging.basicConfig(
            level=level,
            format=log_format,
            handlers=handlers,
        )

    def _on_measurement(self, measurement: ScaleMeasurement):
        """Callback called on each measurement from MQTT."""
        # Measurement already has body_metrics calculated and duplicates filtered

        if not measurement.body_metrics:
            logger.warning("Measurement without body metrics - skipping")
            return

        # Find user
        user = self.users.find_user_by_weight(measurement.weight_kg)
        if not user:
            logger.warning(
                f"Unknown user for weight {measurement.weight_kg}kg - skipping"
            )
            return

        # Log detailed user and body composition summary
        metrics = measurement.body_metrics
        logger.info("=== USER MATCHED ===")
        logger.info(f"User: {user.email}")
        logger.info(f"Weight range: {user.min_weight}-{user.max_weight} kg")
        logger.info("")
        logger.info("=== FINAL RESULTS ===")
        logger.info(f"Weight: {measurement.weight_kg} kg")
        logger.info(f"BMI: {metrics['bmi']:.1f}")
        logger.info(f"Fat: {metrics['percent_fat']:.1f}%")
        logger.info(f"Muscle: {metrics['muscle_mass']:.1f} kg")
        logger.info(f"Bone: {metrics['bone_mass']:.1f} kg")
        logger.info(f"Water: {metrics['percent_hydration']:.1f}%")
        logger.info(f"Visceral: {metrics['visceral_fat_rating']:.1f}")
        logger.info(f"Metabolic age: {metrics['metabolic_age']:.0f}")
        logger.info("====================")

        # Upload to Garmin (only if enabled)
        if self.garmin:
            if self.garmin.login(user.email):
                if self.garmin.upload_body_composition(
                    measurement.timestamp, measurement.body_metrics
                ):
                    logger.info(f"Successfully uploaded to Garmin for {user.email}")
                else:
                    logger.error(f"Failed to upload to Garmin for {user.email}")
        else:
            logger.debug("Garmin upload disabled")

        # Backup to CSV (only if enabled)
        if self.backup:
            self.backup.save(
                user.email, measurement.timestamp, measurement.body_metrics
            )
        else:
            logger.debug("CSV backup disabled")

    def run(self):
        """Run bridge."""
        topic = self.config["mqtt"]["topic"]
        logger.info("Starting MqttScaleGarminBridge")
        logger.info(
            f"MQTT: {self.config['mqtt']['host']}:{self.config['mqtt'].get('port', 1883)}"
        )
        logger.info(f"Topic: {topic}")

        # Auto-configure OMG bridge if enabled
        omg_config = self.config.get("omg_bridge", {})
        if omg_config.get("auto_configure", False):
            try:
                success = self.bridge_configurator.ensure_configured(
                    config_topic=omg_config["config_topic"],
                    status_topic=omg_config["status_topic"],
                    settings=omg_config["settings"],
                )
                if not success:
                    logger.warning(
                        "OMG bridge configuration failed - continuing anyway..."
                    )
            except Exception as e:
                logger.error(f"Failed to configure bridge: {e}")
                logger.warning("Continuing without bridge configuration...")

        self.mqtt.subscribe(topic, self._on_measurement)

        # Graceful shutdown
        def signal_handler(sig, frame):
            logger.info("Shutting down...")
            self.mqtt.stop()
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        self.mqtt.run()


def main():
    parser = argparse.ArgumentParser(description="MQTT Scale to Garmin Bridge")
    parser.add_argument(
        "--config",
        "-c",
        default="config/config.yaml",
        help="Path to config file",
    )
    args = parser.parse_args()

    # Check if config exists
    config_path = Path(args.config)
    if not config_path.exists():
        print(f"Error: Config file not found: {config_path}")
        print("Copy config/config.yaml.example to config/config.yaml and edit it")
        sys.exit(1)

    bridge = MqttScaleGarminBridge(args.config)
    bridge.run()


if __name__ == "__main__":
    main()
