import requests
from decouple import config
from typing import Optional, Dict, Any, List, Tuple, cast
from .base import BaseNotifier


class DiscordNotifier(BaseNotifier):
    """Discord webhook notifier implementation."""

    def __init__(self):
        webhook_url = cast(
            str, config("JSMON_DISCORD_WEBHOOK_URL", default="", cast=str)
        )
        if not webhook_url:
            raise ValueError("JSMON_DISCORD_WEBHOOK_URL is not set")
        self.webhook_url = webhook_url

    def _send_webhook(self, webhook_data: Dict[str, Any]) -> bool:
        """Send a webhook to Discord.

        Args:
            webhook_data: The data to send in the webhook

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            response = requests.post(self.webhook_url, json=webhook_data, timeout=10)
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException as e:
            print(f"Error sending Discord notification: {e}")
            return False

    def _create_fields(self, fields: List[Tuple[str, str]]) -> List[Dict[str, Any]]:
        """Convert field tuples to Discord embed fields.

        Args:
            fields: List of tuples containing (field_name, field_value)

        Returns:
            List of Discord embed field dictionaries
        """
        return [
            {"name": name, "value": value, "inline": True} for name, value in fields
        ]

    def notify_change(
        self,
        endpoint: str,
        fields: List[Tuple[str, str]],
    ) -> bool:
        webhook_data = {
            "username": "JSMon Bot",
            "avatar_url": "https://i.imgur.com/fKL31aD.jpg",
            "embeds": [
                {
                    "title": "JS Endpoint Updated!",
                    "description": f"Endpoint: `{endpoint}`",
                    "color": 3447003,  # Blue color
                    "fields": self._create_fields(fields),
                    "footer": {"text": "JSMon Change Detection"},
                }
            ],
        }
        return self._send_webhook(webhook_data)

    def notify_error(
        self,
        endpoint: str,
        error_message: str,
        fields: List[Tuple[str, str]],
    ) -> bool:
        webhook_data = {
            "username": "JSMon Bot",
            "avatar_url": "https://i.imgur.com/fKL31aD.jpg",
            "embeds": [
                {
                    "title": "JSMon Error Alert",
                    "description": f"Error accessing endpoint: `{endpoint}`",
                    "color": 15158332,  # Red color
                    "fields": [
                        {
                            "name": "Error Message",
                            "value": f"```{error_message}```",
                            "inline": False,
                        },
                        *self._create_fields(fields),
                    ],
                    "footer": {"text": "JSMon Error Detection"},
                }
            ],
        }
        return self._send_webhook(webhook_data)

    def notify_warning(
        self,
        endpoint: str,
        warning_message: str,
        fields: List[Tuple[str, str]],
    ) -> bool:
        webhook_data = {
            "username": "JSMon Bot",
            "avatar_url": "https://i.imgur.com/fKL31aD.jpg",
            "embeds": [
                {
                    "title": "JSMon Warning Alert",
                    "description": f"Warning for endpoint: `{endpoint}`",
                    "color": 16776960,  # Yellow color
                    "fields": [
                        {
                            "name": "Warning Message",
                            "value": f"```{warning_message}```",
                            "inline": False,
                        },
                        *self._create_fields(fields),
                    ],
                    "footer": {"text": "JSMon Warning Detection"},
                }
            ],
        }
        return self._send_webhook(webhook_data)
