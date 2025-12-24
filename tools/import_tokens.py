#!/usr/bin/python3
"""
Generate OAuth tokens for Garmin Connect.
Based on: https://github.com/RobertWojtowicz/export2garmin
"""

import os
import sys
from getpass import getpass
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import requests
    from garminconnect import Garmin, GarminConnectAuthenticationError
    from garth.exc import GarthHTTPError
except ImportError as e:
    print(f"Missing dependency: {e}")
    print("Run: pip install garminconnect")
    sys.exit(1)


def get_credentials():
    """Get user credentials from input."""
    email = input("Login e-mail: ")
    password = getpass("Enter password: ")
    return email, password


def get_mfa():
    """Get MFA code from input."""
    return input("MFA/2FA one-time code: ")


def init_api(tokens_dir: Path, is_cn: bool = False):
    """
    Initialize Garmin API and save OAuth tokens.

    Args:
        tokens_dir: Directory to save tokens
        is_cn: True for China servers, False for international
    """
    try:
        email, password = get_credentials()
        garmin = Garmin(email, password, is_cn=is_cn, return_on_mfa=True)
        result1, result2 = garmin.login()

        if result1 == "needs_mfa":
            mfa_code = get_mfa()
            garmin.resume_login(result2, mfa_code)

        # Create tokens directory if not exists
        tokens_dir.mkdir(parents=True, exist_ok=True)

        # Save OAuth tokens as base64 encoded string
        token_base64 = garmin.garth.dumps()
        token_file = tokens_dir / email

        with open(token_file, "w") as f:
            f.write(token_base64)

        print(f"OAuth tokens saved to: {token_file}")
        return True

    except (
        FileNotFoundError,
        GarthHTTPError,
        GarminConnectAuthenticationError,
        requests.exceptions.HTTPError,
    ) as err:
        print(f"Error: {err}")
        return False


def main():
    """Main entry point."""
    print(
        """
==============================================
MqttScaleGarminBridge - Import Garmin Tokens
==============================================
"""
    )

    # Default tokens directory
    script_dir = Path(__file__).parent.parent
    tokens_dir = script_dir / "data" / "tokens"

    print(f"Tokens will be saved to: {tokens_dir}")
    print()

    # Ask if China server
    is_cn_input = input("Use China server? (y/N): ").strip().lower()
    is_cn = is_cn_input == "y"

    success = init_api(tokens_dir, is_cn)

    if success:
        print("\nDone! You can now run the bridge.")
    else:
        print("\nFailed to generate tokens. Please try again.")
        sys.exit(1)


if __name__ == "__main__":
    main()
