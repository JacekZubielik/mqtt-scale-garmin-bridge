"""OpenMQTTGateway Bridge Configurator."""

import json
import logging
import time
from typing import Any, Dict

import paho.mqtt.client as mqtt

logger = logging.getLogger(__name__)


class BridgeConfigurator:
    """Configures OpenMQTTGateway bridge via MQTT commands."""

    def __init__(self, host: str, port: int = 1883):
        self.host = host
        self.port = port

    def configure(self, config_topic: str, settings: Dict[str, Any], wait_seconds: int = 5):
        """
        Configure OMG bridge with provided settings.

        Args:
            config_topic: MQTT topic for bridge configuration
            settings: Dictionary of bridge settings
            wait_seconds: Time to wait between commands
        """
        logger.info("Configuring OpenMQTTGateway bridge...")

        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

        try:
            client.connect(self.host, self.port, keepalive=60)
            client.loop_start()

            # Send each setting separately with delay
            for key, value in settings.items():
                if key == "save":
                    continue  # Handle save at the end

                command = json.dumps({key: value})
                logger.info(f"Sending bridge config: {key}={value}")
                client.publish(config_topic, command)
                time.sleep(2)  # Wait between commands

            # Save configuration at the end
            if settings.get("save", False):
                save_command = json.dumps({"save": True})
                logger.info("Saving bridge configuration...")
                client.publish(config_topic, save_command)
                time.sleep(2)

            logger.info(
                f"Bridge configuration complete. Waiting {wait_seconds}s for bridge to apply settings..."
            )
            time.sleep(wait_seconds)

        except Exception as e:
            logger.error(f"Failed to configure bridge: {e}")
            raise
        finally:
            client.loop_stop()
            client.disconnect()

        logger.info("Bridge configuration finished.")
