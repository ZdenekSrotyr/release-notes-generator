# Release Notes Generator

A simple tool for automatic generation of release notes into separate files for components and repositories in the Keboola organization.

## Table of Contents
- [Overview](#overview)
- [Features](#features)
- [Installation](#installation)
- [Usage](#usage)
  - [Quick Start](#quick-start)
  - [Command Line Parameters](#command-line-parameters)
  - [Environment Variables](#environment-variables)
- [AI Summary](#ai-summary)
- [GitHub Actions](#github-actions)
- [Slack Integration](#slack-integration)
- [Last Run Detection](#last-run-detection)
- [Performance Optimization](#performance-optimization)
- [Release Notes Logic](#release-notes-logic)
- [Customizing Output](#customizing-output)
- [Release Notes Structure](#release-notes-structure)

## Overview

This tool automatically scans GitHub repositories, looks for new tags, and creates structured release notes for each new component version. The process is fully automated and can run as a scheduled GitHub Action.

## Features

✅ Automatic discovery of repositories containing "component" in their name within the Keboola organization  
✅ Component name extraction from `.github/workflows/push.yml` (KBC_DEVELOPERPORTAL_APP)  
✅ Retrieval of changes between tags and pull request information  
✅ Chronological ordering of releases by tag date  
✅ Slack integration for sharing new release notes  
✅ GitHub Actions support for automatic generation  
✅ Separate release notes files for each component release in the `release_notes` directory  
✅ Automatic detection of the last generated release  
✅ **AI summary of changes using OpenAI API** (optional)  
✅ **Optimized tag search** for performance with large repositories  
✅ **Extended timeframe** - searches for releases within the last 30 days by default  
✅ **Smart filtering** - only creates release notes when actual changes exist between tags

## Installation

```bash
# Clone the repository
git clone https://github.com/keboola/release-notes-generator.git
cd release-notes-generator

# Install dependencies
pip install -r requirements.txt
```

## Usage

### Quick Start

```bash
# Set GitHub token (required)
export GITHUB_TOKEN="ghp_your_token_here"

# Basic usage - generates release notes from the last 30 days
python main.py
```

### Command Line Parameters

```bash
# Generate from the last run
python main.py --since-last-run

# Enable Slack notifications (requires webhook URL)
export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/xxx/yyy/zzz"
python main.py --slack

# Example with AI summary
export OPENAI_API_KEY="sk-your_openai_api_key_here"
python main.py --ai-summary

# Complete example
python main.py --since-last-run --slack --ai-summary
```

### All Command Line Parameters

```
--since-last-run    Generate from the date of the last file in the release_notes directory
--slack             Enable sending notifications to Slack
--ai-summary        Generate AI summary of changes (requires OPENAI_API_KEY)
```

### Environment Variables

The following environment variables are used:

- `GITHUB_TOKEN` - GitHub API token (required)
- `SLACK_WEBHOOK_URL` - Slack webhook URL (for Slack notifications)
- `OPENAI_API_KEY` - OpenAI API key (for AI summaries)

## AI Summary

The tool supports automatic generation of change summaries using artificial intelligence (OpenAI):

1. To use this feature, set the `--ai-summary` parameter at startup
2. Set the `OPENAI_API_KEY` environment variable with a valid OpenAI API key
3. A summary of changes between tags will be automatically generated

**Benefits of AI Summarization:**
- Creates concise and clear summaries of technical changes (max. 150 words)
- Identifies and highlights the most important changes in the release
- Complements the detailed list of changes with a quick overview for better understanding
- Facilitates rapid comprehension of the essence of a new release

**Technical Details:**
- Uses the GPT-3.5 Turbo model from OpenAI
- Analyzes commit and PR titles
- The result is displayed in the "AI Summary" section in the release notes

## GitHub Actions

The included GitHub Actions workflow allows:

1. Generating release notes automatically on a schedule
2. Running generation manually with custom parameters
3. Committing new release notes directly to the repository
4. Optionally sending notifications to Slack
5. Optionally generating AI summaries of changes

### GitHub Actions Setup

1. Add secrets to your GitHub repository:
   - `GITHUB_TOKEN` (provided automatically)
   - `SLACK_WEBHOOK_URL` (for Slack notifications)
   - `OPENAI_API_KEY` (for AI summary)

2. The workflow can be triggered:
   - Manually from the Actions tab with parameter options
   - Automatically according to a schedule (uncomment the `schedule` section in `.github/workflows/generate-release-notes.yml`)

## Slack Integration

Share release notes with your team via Slack:

1. Set the `--slack` parameter when running the tool
2. Provide the webhook URL via the `SLACK_WEBHOOK_URL` environment variable

The Slack message includes:
- List of components that were updated
- Tag names and release dates
- Up to 3 changes for each tag with a link to GitHub
- Information about the total number of changes

## Last Run Detection

The `--since-last-run` parameter automatically detects the date of the last file in the `release_notes` directory and generates new items from that date. This is useful for:

1. Incremental updates without manual date input
2. Ensuring no releases are missed between runs
3. Automated regular updates via GitHub Actions

## Performance Optimization

The tool implements several optimizations to speed up tag searching, especially for repositories with many tags:

1. **Efficient API Usage**:
   - Directly searches most recent 100 tags without the need to fetch all commits first
   - Sets time window to 30 days by default to capture more releases
   - Ensures end dates include the full day (23:59:59) to catch all changes

2. **Smart Tag Filtering**:
   - Applies date filters directly to tags for more accurate results
   - Uses more robust error handling for individual tag processing
   - Provides detailed date range information in logs

3. **Fallback Mechanisms**:
   - Handles problematic tags gracefully without failing the entire process
   - Provides detailed logging for troubleshooting

These optimizations significantly reduce processing time and improve reliability, especially for organizations with many repositories or repositories with extensive tag histories.

## Release Notes Logic

The tool follows specific logic when determining which release notes to generate:

1. **Change Detection**:
   - Only creates release notes when actual changes exist between tags
   - Skips tags that have no code changes or commits between them
   - Logs information about skipped releases for monitoring

2. **De-duplication**:
   - Checks if a release note already exists for a specific tag before creating it
   - Uses file naming based on tag timestamp to ensure uniqueness
   - Prevents duplicate release notes when running the tool multiple times

3. **Incremental Processing**:
   - With `--since-last-run`, only processes new tags since the last execution
   - Efficiently handles new tags without reprocessing existing ones

This approach ensures that the release notes are meaningful and represent actual changes in the codebase.

## Customizing Output

Customize the output by modifying the template in the `templates` directory. The template for component release notes is `component-release.md.j2`, which uses the Jinja2 format.

### Template Structure

The template includes sections:
- Header with component name and tag
- Release date and links to GitHub
- AI summary of changes (if available)
- List of all changes with links to pull requests
- Metadata about generation

## Release Notes Structure

The tool generates separate release notes files for each component release:

1. Each component release is stored as a separate file in the `release_notes` directory
2. Files are named in the format `YYYY-MM-DD-HH-MM-SS_tag_component-name.md`
3. This allows better organization and tracking of releases by component

This feature helps with:
- Tracking which releases have already been processed
- Creating a structured archive of all component releases
- Simplifying the process of reporting on new releases
- Ability to easily search for release history for a specific component 