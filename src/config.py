#!/usr/bin/env python3
import os
import logging

# GitHub Configuration
GITHUB_ORGANIZATION = "keboola"
REPO_PATTERNS = "component"
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")

# Directory and File Paths
TEMPLATE_DIR = "templates"
RELEASE_NOTES_DIR = "release_notes"

# API Endpoints
KEBOOLA_STORAGE_API_URL = "https://connection.keboola.com/v2/storage"

# Slack Configuration
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL")

# OpenAI Configuration
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
OPENAI_MODEL = "gpt-3.5-turbo"

# Logging Configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('release-notes-generator')
