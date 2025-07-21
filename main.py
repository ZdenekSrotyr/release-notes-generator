#!/usr/bin/env python3
"""
Main script for generating release notes in Keboola environment.
"""
import os
import sys
import traceback
from keboola.component import CommonInterface

# Add the project root directory to the Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# Import from src
from src.config import logger
from src.generator import ReleaseNotesGenerator
from src.config import load_configuration, validate_configuration


def main():
    """Main function for Keboola component."""
    logger.info("Starting Release Notes Generator")
    logger.info(f"Current working directory: {os.getcwd()}")
    logger.info(f"Python path: {sys.path[:3]}...")  # Show first 3 paths

    try:
        # Check if we're in Keboola environment
        if 'KBC_DATADIR' in os.environ:
            logger.info("Detected Keboola environment")
            ci = CommonInterface()
        else:
            logger.info("Running in local environment - using data/ directory")
            # For local testing, use the data directory
            data_dir = os.path.join(project_root, 'data')
            if not os.path.exists(data_dir):
                logger.error(f"Data directory not found: {data_dir}")
                logger.info("Please create data/ directory with config.json for local testing")
                sys.exit(1)

            # Set environment variable for CommonInterface
            os.environ['KBC_DATADIR'] = data_dir
            ci = CommonInterface()

        logger.info("Keboola CommonInterface initialized successfully")
        logger.info(f"Data directory: {ci.data_folder_path}")



        # Load and validate configuration
        logger.info("Loading configuration...")
        config = load_configuration(ci)
        logger.info("Configuration loaded successfully")

        if not validate_configuration(config):
            logger.error("Configuration validation failed")
            sys.exit(1)

        # Create generator
        logger.info("Creating ReleaseNotesGenerator...")
        generator = ReleaseNotesGenerator(config.github_token, ci)

        # Generate timeline
        logger.info("Starting release notes generation...")
        releases = generator.generate_timeline()

        logger.info(f"Processing completed. Generated {len(releases)} new release notes.")

    except Exception as e:
        logger.error(f"Error during processing: {e}")
        logger.error(f"Full traceback:")
        logger.error(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()
