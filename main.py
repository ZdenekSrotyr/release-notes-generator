#!/usr/bin/env python3
"""
Main script for generating release notes.
"""
import os
import sys
import argparse
import glob
import datetime

# Add the project root directory to the Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# Import from src
from src.config import GH_TOKEN, logger, RELEASE_NOTES_DIR
from src.generator import ReleaseNotesGenerator
from src.slack_utils import send_slack_message


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Generate release notes for Keboola components.")

    # Add parameters
    parser.add_argument("--slack", action="store_true",
                        help="Send Slack notification for new releases")
    parser.add_argument("--notify-only", action="store_true",
                        help="Only send notifications for existing releases, don't generate new ones")

    return parser.parse_args()


def setup_environment():
    """Setup environment and validate required configurations."""
    # Create release notes directory if it doesn't exist
    os.makedirs(RELEASE_NOTES_DIR, exist_ok=True)

    # Check GitHub token if we need it
    if not GH_TOKEN:
        logger.error("GitHub token not provided. Set GH_TOKEN environment variable.")
        sys.exit(1)

    # Date range will be automatically determined in the ReleaseNotesGenerator class
    return GH_TOKEN


def mark_as_notified(file_path):
    """Mark a file as having been notified about."""
    try:
        # Create a marker file to indicate this release note has been sent to Slack
        with open(f"{file_path}.notified", 'w') as f:
            f.write(datetime.datetime.now().isoformat())
        logger.info(f"Marked {file_path} as notified")
        return True
    except Exception as e:
        logger.error(f"Error marking {file_path} as notified: {e}")
        return False


def notify_pending_releases():
    """Send notifications for pending releases - simply send the markdown content of each file."""
    logger.info("Looking for pending release notes to notify about")

    # Get all release note files
    all_files = glob.glob(f"{RELEASE_NOTES_DIR}/*.md")
    pending_files = [f for f in all_files if not os.path.exists(f"{f}.notified")]

    if not pending_files:
        logger.info("No pending releases to notify about")
        return False

    logger.info(f"Found {len(pending_files)} pending release notes to notify about")
    success_count = 0

    # Process each file individually
    for file_path in pending_files:
        try:
            # Read file content
            with open(file_path, 'r') as f:
                content = f.read()

            # Send notification with the file content
            if send_slack_message(content):
                # If successful, mark it as notified immediately
                if mark_as_notified(file_path):
                    success_count += 1
        except Exception as e:
            logger.error(f"Error sending notification for {file_path}: {e}")

    logger.info(f"Successfully sent and marked {success_count} of {len(pending_files)} notifications")
    return success_count > 0


def main():
    """Main function."""
    args = parse_args()

    # If only sending notifications for existing release notes
    if args.notify_only:
        logger.info("Running in notify-only mode")
        notify_pending_releases()
        return

    # Setup environment
    github_token = setup_environment()

    # Create generator - all time period detection is handled internally
    generator = ReleaseNotesGenerator(
        github_token=github_token
    )

    # Generate release notes
    generator.generate_timeline()

    # Send Slack notification if requested
    if args.slack:
        notify_pending_releases()

    logger.info("Done!")


if __name__ == "__main__":
    main()
