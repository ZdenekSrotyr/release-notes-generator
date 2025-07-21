#!/usr/bin/env python3
import os
import logging
import sys
from typing import Optional
from pydantic import BaseModel

# GitHub Configuration
GITHUB_ORGANIZATION = "keboola"
REPO_PATTERNS = "component"



# Google AI Configuration
GOOGLE_AI_MODEL = "gemini-2.5-pro-preview-03-25"

# Logging Configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    force=True,
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('release-notes-generator')
# Ensure logs are not buffered
for handler in logger.handlers:
    handler.setStream(sys.stdout)


class Configuration(BaseModel):
    """Configuration model for the release notes generator."""
    github_token: str
    google_ai_api_key: Optional[str] = None
    days_back: int = 7
    table_name: str = "component_releases"


def load_configuration(ci) -> Configuration:
    """Load configuration from Keboola component parameters."""
    try:
        # Get parameters from Keboola
        params = ci.configuration.parameters
        logger.info(f"Loaded parameters: {list(params.keys())}")
        logger.info(f"Parameter values: {params}")
        
        # Handle encrypted parameters (those with # prefix)
        config_data = {}
        
        # Map encrypted parameters to our model fields
        if 'github_token' in params:
            config_data['github_token'] = params['github_token']
            logger.info("Found github_token in parameters")
        elif '#github_token' in params:
            config_data['github_token'] = params['#github_token']
            logger.info("Found #github_token in parameters")
        else:
            logger.error("No github_token found in configuration")
            logger.error(f"Available parameters: {list(params.keys())}")
            raise ValueError("GitHub token is required. Please add 'github_token' or '#github_token' to your configuration.")
            
        if 'google_ai_api_key' in params:
            config_data['google_ai_api_key'] = params['google_ai_api_key']
            logger.info("Found google_ai_api_key in parameters")
        elif '#google_ai_api_key' in params:
            config_data['google_ai_api_key'] = params['#google_ai_api_key']
            logger.info("Found #google_ai_api_key in parameters")
        else:
            logger.info("No Google AI API key found - AI summaries will be disabled")
            
        # Handle regular parameters
        config_data['days_back'] = params.get('days_back', 7)
        config_data['table_name'] = params.get('table_name', 'component_releases')
        
        logger.info(f"Configuration data prepared: {list(config_data.keys())}")
        logger.info(f"Config data values: {config_data}")
        
        # Create configuration object
        config = Configuration(**config_data)
        
        logger.info(f"Configuration loaded successfully: days_back={config.days_back}, table_name={config.table_name}")
        return config
        
    except Exception as e:
        logger.error(f"Error loading configuration: {e}")
        logger.error(f"Available parameters: {list(ci.configuration.parameters.keys()) if hasattr(ci, 'configuration') and hasattr(ci.configuration, 'parameters') else 'No parameters available'}")
        raise


def validate_configuration(config: Configuration) -> bool:
    """Validate the configuration and log any issues."""
    issues = []
    
    if not config.github_token:
        issues.append("GitHub token is required")
    
    if config.days_back <= 0:
        issues.append("days_back must be positive")
    
    if not config.table_name:
        issues.append("table_name cannot be empty")
    
    if issues:
        for issue in issues:
            logger.error(f"Configuration validation error: {issue}")
        return False
    
    logger.info("Configuration validation passed")
    return True
