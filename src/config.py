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

# Google AI Configuration
GOOGLE_AI_API_KEY = os.environ.get("GOOGLE_AI_API_KEY")
GOOGLE_AI_MODEL = "gemini-2.5-pro-preview-03-25"

# Logging Configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('release-notes-generator')
