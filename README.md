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
- [Component Details](#component-details)

## Overview

This tool automatically scans GitHub repositories, looks for new tags, and creates structured release notes for each new component version. The process is fully automated and can run as a scheduled GitHub Action.

## Features

✅ Automatic discovery of repositories containing "component" in their name within the Keboola organization  
✅ Component name extraction from all `.github/*.yml` files (KBC_DEVELOPERPORTAL_APP)  
✅ Support for multiple components defined in a single repository  
✅ Retrieval of changes between tags and pull request information  
✅ Chronological ordering of releases by tag date  
✅ Slack integration for sharing new release notes  
✅ GitHub Actions support for automatic generation  
✅ Separate release notes files for each component release in the `release_notes` directory  
✅ Automatic detection of the last generated release  
✅ **AI summary of changes using OpenAI API** (optional)  
✅ **Component details** from Keboola Connection Storage API  
✅ **Component maturity level** detection (Experimental, Beta, GA)  
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
# Basic usage - uses the last run date, or 30 days if no previous runs
python main.py

# Enable Slack notifications (requires webhook URL)
export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/xxx/yyy/zzz"
python main.py --slack

# Use OpenAI API for AI summaries (automatically enabled if API key is available)
export OPENAI_API_KEY="sk-your_openai_api_key_here"
python main.py
```

### All Command Line Parameters

```
--slack             Enable sending notifications to Slack
```

### Environment Variables

The following environment variables are used:

- `GITHUB_TOKEN` - GitHub API token (required)
- `SLACK_WEBHOOK_URL` - Slack webhook URL (for Slack notifications)
- `OPENAI_API_KEY` - OpenAI API key (for AI summaries)

### Feature Auto-detection

The tool uses environment detection to enable features:

- **Date Range**: Automatically determined from the latest release note file, or defaults to the last 30 days if no files exist
- **AI Summaries**: Automatically enabled if the `OPENAI_API_KEY` environment variable is set
- **Slack Notifications**: Enabled with the `--slack` parameter and requires the `SLACK_WEBHOOK_URL` environment variable

## AI Summary

The tool supports automatic generation of change summaries using artificial intelligence (OpenAI):

1. To use this feature, set the `OPENAI_API_KEY` environment variable with a valid OpenAI API key
2. A summary of changes between tags will be automatically generated
3. No additional parameters are needed - the feature is automatically enabled when the API key is detected

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
5. Automatically generating AI summaries if OpenAI API key is provided

### GitHub Actions Setup

1. Add secrets to your GitHub repository:
   - `GITHUB_TOKEN` (provided automatically)
   - `SLACK_WEBHOOK_URL` (for Slack notifications, optional)
   - `OPENAI_API_KEY` (for AI summary, optional)

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

The tool automatically detects the date of the last file in the `release_notes` directory and generates new items from that date. This is useful for:

1. Incremental updates without manual date input
2. Ensuring no releases are missed between runs
3. Automated regular updates via GitHub Actions

If no previous release notes are found, the tool defaults to the last 30 days.

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
   - The tool automatically processes new tags since the last execution
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
2. Files are named in the format `YYYY-MM-DD-HH-MM-SS_tag_component-name_stage.md`, where:
   - The timestamp reflects when the tag was created
   - `tag` is the version number (e.g., `1.2.3`)
   - `component-name` is the normalized component name
   - `stage` indicates the component maturity level (`experimental`, `beta`, or `ga`)
3. This allows better organization and tracking of releases by component and maturity level

This feature helps with:
- Tracking which releases have already been processed
- Creating a structured archive of all component releases
- Simplifying the process of reporting on new releases
- Ability to easily search for release history for a specific component
- Quick identification of experimental or beta components

## Component Details

The tool now enriches release notes with detailed information about the component from the Keboola Connection Storage API:

1. For each component, the tool fetches details like:
   - Component type
   - Component name and description
   - Component stage (Experimental, Beta, or GA) based on component flags
   - URI and documentation links if available

**Benefits of Component Details:**
- Provides more context about the component in release notes
- Clearly indicates the maturity level of each component
- Links to official documentation and resources
- Makes release notes more informative and useful

**Technical Details:**
- Uses the public Keboola Connection Storage API (https://connection.keboola.com/v2/storage)
- No authentication required to access the components list
- Efficiently searches for component details by component ID
- Automatically determines component stage based on flags:
  - `appinfo.experimental` flag indicates Experimental stage
  - `appinfo.beta` flag indicates Beta stage
  - Components without these flags are considered GA (Generally Available)
- Details are displayed in a dedicated section in the release notes 