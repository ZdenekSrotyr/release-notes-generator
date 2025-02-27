#!/usr/bin/env python3
import json
import requests
from src.config import logger, SLACK_WEBHOOK_URL

def send_slack_notification(new_releases):
    """Send a Slack notification about new releases."""
    if not SLACK_WEBHOOK_URL:
        logger.info("Slack webhook URL not provided, skipping notification")
        return False

    if not new_releases:
        logger.info("No new releases to notify about")
        return False

    logger.info(f"Sending Slack notification about {len(new_releases)} new releases")

    try:
        # Create message blocks
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"🚀 New Component Releases ({len(new_releases)})"
                }
            },
            {
                "type": "divider"
            }
        ]

        # Add each release to the message
        for release in new_releases[:10]:  # Limit to 10 to avoid message size limits
            component_name = release['component_name']
            tag_name = release['tag_name']
            repo_name = release['repo_name']
            tag_url = release['tag_url']
            date = release['date'].strftime('%Y-%m-%d')
            component_stage = release['component_stage']

            # Special formatting for experimental and beta components
            stage_emoji = "🚀"  # Default for GA
            if component_stage == "Experimental":
                stage_emoji = "🧪"
            elif component_stage == "Beta":
                stage_emoji = "⚠️"

            # Add component details if available
            component_description = ""
            if release.get('component_details') and release['component_details'].get('description'):
                component_description = release['component_details']['description']

            # Add section for this release
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{stage_emoji} {component_name} {tag_name}*\n{date} | {repo_name}\n{component_description}"
                },
                "accessory": {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "View Release"
                    },
                    "url": tag_url
                }
            })

            # Add a divider
            blocks.append({
                "type": "divider"
            })

        # If there are more than 10 releases, add a note
        if len(new_releases) > 10:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"_...and {len(new_releases) - 10} more releases_"
                }
            })

        # Create the final message
        message = {
            "blocks": blocks
        }

        # Send to Slack
        response = requests.post(
            SLACK_WEBHOOK_URL,
            data=json.dumps(message),
            headers={'Content-Type': 'application/json'}
        )

        if response.status_code == 200:
            logger.info("Slack notification sent successfully")
            return True
        else:
            logger.error(f"Error sending Slack notification: {response.status_code} {response.text}")
            return False

    except Exception as e:
        logger.error(f"Error sending Slack notification: {e}")
        return False 