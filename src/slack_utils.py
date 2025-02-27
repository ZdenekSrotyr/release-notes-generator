#!/usr/bin/env python3
import json
import requests
from src.config import logger, SLACK_WEBHOOK_URL


def send_slack_message(file_content):
    """Send a Slack notification with the markdown content of a release note."""
    if not SLACK_WEBHOOK_URL:
        logger.info("Slack webhook URL not provided, skipping notification")
        return False

    try:
        # Slack supports many markdown elements naturally
        # Create a simple message with the markdown content
        message = {
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": file_content
                    }
                }
            ]
        }

        # Send to Slack
        response = requests.post(
            SLACK_WEBHOOK_URL,
            data=json.dumps(message),
            headers={'Content-Type': 'application/json'}
        )

        if response.status_code == 200:
            logger.info(f"Slack notification sent successfully")
            return True
        else:
            logger.error(f"Error sending Slack notification: {response.status_code} {response.text}")
            return False

    except Exception as e:
        logger.error(f"Error sending Slack notification: {e}")
        return False
