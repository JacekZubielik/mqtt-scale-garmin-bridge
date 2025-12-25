"""OpenMQTTGateway Bridge Configurator."""

import json
import logging
import time
from typing import Any, Optional

import paho.mqtt.client as mqtt

logger = logging.getLogger(__name__)


class BridgeConfigurator:
    """Configures OpenMQTTGateway bridge via MQTT commands."""

    def __init__(
        self,
        host: str,
        port: int = 1883,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ):
        self.host = host
        self.port = port
        self.username = username
        self.password = password

    def _create_client(self) -> mqtt.Client:
        """Create and configure MQTT client."""
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        if self.username and self.password:
            client.username_pw_set(self.username, self.password)
        return client

    def get_current_settings(
        self,
        status_topic: str,
        config_topic: str,
        timeout: int = 10,
    ) -> Optional[dict[str, Any]]:
        """
        Get current OMG settings by requesting config dump.

        Sends {"dump": true} to config_topic and waits for response on status_topic.

        Args:
            status_topic: Topic where OMG publishes BLE status (e.g., home/OMG_ESP32_BLE/BTtoMQTT)
            config_topic: Topic to send dump request to
            timeout: Seconds to wait for response

        Returns:
            Current settings dict or None if not received
        """
        result: dict[str, Any] = {"received": False, "settings": None}

        def on_connect(client, userdata, flags, reason_code, properties):
            if reason_code == 0:
                client.subscribe(status_topic)
                logger.debug(f"Subscribed to {status_topic}")
                # Request config dump
                time.sleep(0.3)
                client.publish(config_topic, json.dumps({"dump": True}))
                logger.debug(f"Sent dump request to {config_topic}")

        def on_message(client, userdata, msg):
            try:
                payload = json.loads(msg.payload.decode())
                # Check if this is BLE config message (has bleconnect key)
                if "bleconnect" in payload or "interval" in payload:
                    result["settings"] = payload
                    result["received"] = True
            except json.JSONDecodeError:
                pass

        client = self._create_client()
        client.on_connect = on_connect
        client.on_message = on_message

        try:
            client.connect(self.host, self.port, keepalive=60)
            client.loop_start()

            # Wait for settings message
            start_time = time.time()
            while not result["received"] and (time.time() - start_time) < timeout:
                time.sleep(0.1)

            settings: Optional[dict[str, Any]] = result["settings"]
            return settings

        except Exception as e:
            logger.error(f"Failed to get current settings: {e}")
            return None
        finally:
            client.loop_stop()
            client.disconnect()

    def check_settings(
        self,
        status_topic: str,
        config_topic: str,
        expected_settings: dict[str, Any],
        timeout: int = 10,
    ) -> tuple[bool, dict[str, Any]]:
        """
        Check if current OMG settings match expected settings.

        Args:
            status_topic: Topic where OMG publishes status
            config_topic: Topic to send dump request to
            expected_settings: Settings we want to verify
            timeout: Seconds to wait for response

        Returns:
            Tuple of (all_match: bool, current_settings: dict)
        """
        current = self.get_current_settings(status_topic, config_topic, timeout)

        if current is None:
            logger.warning("Could not retrieve current OMG settings")
            return False, {}

        # Check each expected setting
        mismatches = {}
        for key, expected_value in expected_settings.items():
            if key == "save":
                continue  # Skip save flag

            current_value = current.get(key)
            if current_value != expected_value:
                mismatches[key] = {"current": current_value, "expected": expected_value}

        if mismatches:
            logger.info(f"Settings mismatch: {mismatches}")
            return False, current

        return True, current

    def configure(
        self,
        config_topic: str,
        settings: dict[str, Any],
        status_topic: Optional[str] = None,
        verify: bool = True,
        force: bool = False,
    ) -> bool:
        """
        Configure OMG bridge with provided settings.

        New flow:
        1. Check current settings (if status_topic provided and not force)
        2. If settings match - skip configuration
        3. If settings don't match - apply new settings
        4. Verify settings were applied (if verify=True)

        Args:
            config_topic: MQTT topic for bridge configuration commands
            settings: Dictionary of bridge settings to apply
            status_topic: Topic where OMG publishes status (for verification)
            verify: Whether to verify settings after applying
            force: Force reconfiguration even if settings match

        Returns:
            True if configuration successful or already correct, False otherwise
        """
        # Step 1: Check current settings (unless force mode)
        if status_topic and not force:
            logger.info("Checking current OMG bridge settings...")
            settings_ok, current = self.check_settings(
                status_topic, config_topic, settings
            )

            if settings_ok:
                logger.info(
                    "OMG bridge settings already correct - skipping configuration"
                )
                return True

            if current:
                logger.info("OMG bridge settings need update")

        # Step 2: Apply new settings
        logger.info("Configuring OpenMQTTGateway bridge...")

        client = self._create_client()

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
                "Bridge configuration sent. Waiting for bridge to apply settings..."
            )
            time.sleep(5)

        except Exception as e:
            logger.error(f"Failed to configure bridge: {e}")
            return False
        finally:
            client.loop_stop()
            client.disconnect()

        # Step 3: Verify settings (if requested and status_topic provided)
        if verify and status_topic:
            logger.info("Verifying OMG bridge settings...")
            settings_ok, current = self.check_settings(
                status_topic, config_topic, settings, timeout=15
            )

            if settings_ok:
                logger.info("OMG bridge configuration verified successfully")
                return True
            else:
                logger.error("OMG bridge configuration verification FAILED")
                logger.error(f"Current settings: {current}")
                return False

        logger.info("Bridge configuration finished (verification skipped)")
        return True

    def ensure_configured(
        self,
        config_topic: str,
        status_topic: str,
        settings: dict[str, Any],
        max_retries: int = 2,
    ) -> bool:
        """
        Ensure OMG bridge is properly configured, with retries.

        This is the main entry point for bridge configuration.

        Args:
            config_topic: MQTT topic for configuration commands
            status_topic: Topic where OMG publishes status
            settings: Expected settings
            max_retries: Number of configuration attempts

        Returns:
            True if bridge is properly configured
        """
        for attempt in range(max_retries + 1):
            if attempt > 0:
                logger.info(f"Retry attempt {attempt}/{max_retries}")

            success = self.configure(
                config_topic=config_topic,
                settings=settings,
                status_topic=status_topic,
                verify=True,
                force=(attempt > 0),  # Force on retries
            )

            if success:
                return True

            time.sleep(3)

        logger.error(f"Failed to configure OMG bridge after {max_retries + 1} attempts")
        return False
