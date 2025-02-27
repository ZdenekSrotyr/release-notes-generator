#!/usr/bin/env python3
import os
import sys
import argparse

from src.config import GITHUB_TOKEN, logger, RELEASE_NOTES_DIR
from src.generator import ReleaseNotesGenerator

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Generate release notes for Keboola components.")
    
    # Only keep the slack parameter
    parser.add_argument("--slack", action="store_true", 
                       help="Send Slack notification for new releases")
    
    return parser.parse_args()

def setup_environment():
    """Setup environment and validate required configurations."""
    # Create release notes directory if it doesn't exist
    os.makedirs(RELEASE_NOTES_DIR, exist_ok=True)
    
    # Check GitHub token
    if not GITHUB_TOKEN:
        logger.error("GitHub token not provided. Set GITHUB_TOKEN environment variable.")
        sys.exit(1)
    
    # Date range will be automatically determined in the ReleaseNotesGenerator class
    return GITHUB_TOKEN

def main():
    """Main function."""
    args = parse_args()
    
    # Setup environment
    github_token = setup_environment()
    
    # Create generator - all time period detection is handled internally
    generator = ReleaseNotesGenerator(
        github_token=github_token
    )
    
    # Generate release notes
    timeline = generator.generate_timeline()
    logger.info(f"Generated timeline with {len(timeline)} entries")
    
    # Send Slack notification if requested
    if args.slack:
        generator.send_slack_notification()
    
    logger.info("Done!")

if __name__ == "__main__":
    main()
