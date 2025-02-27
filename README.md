# Release Notes Generator

A tool for automatically generating chronological release notes for components and repositories.

## Features

- Automatic discovery of repositories containing "component" in the name
- Extraction of component name from `.github/workflows/push.yml` (KBC_DEVELOPERPORTAL_APP)
- Retrieval of changes between tags and information from pull requests
- Chronological ordering of release notes by tag date
- AI-powered description of changes between tags
- Slack integration for sharing release notes
- GitHub Actions support for automated generation
- Command line arguments for flexible configuration
- Ability to generate from the last successful run
- Customizable time period for generating release notes
- Individual release notes for each component in a separate file
- Option to process and notify only about new releases that weren't processed before

## Installation

```bash
# Clone the repository
git clone https://github.com/your-org/release-notes-generator.git
cd release-notes-generator

# Install dependencies
pip install -r requirements.txt
```

## Usage

### Command Line Options

```bash
# Set GitHub token (required)
export GITHUB_TOKEN="ghp_your_token_here"

# Basic usage - generates release notes for last month
python main.py

# Specify time period
python main.py -t last-week

# Generate for a specific repository
python main.py -r keboola-component-example

# Generate from last successful run
python main.py --since-last-run

# Enable AI-powered descriptions (requires OpenAI API key)
export AI_API_KEY="your_openai_api_key"
python main.py --use-ai

# Enable Slack notifications (requires webhook URL)
export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/xxx/yyy/zzz"
python main.py --slack-enabled

# Only process and notify about new releases
python main.py --only-new-releases --slack-enabled

# Specify custom directory for individual release notes
python main.py --release-notes-dir="releases/2023"

# Full options example
python main.py -o keboola -t last-month -r my-component --since-last-run --use-ai --slack-enabled --only-new-releases -v
```

### All Command Line Arguments

```
-o, --organization      GitHub organization (default: keboola)
-r, --repo              Generate for a single repository
-p, --repo-patterns     Repository search patterns (comma separated, default: component)
--repos                 Explicitly listed repositories (comma separated)
-t, --time-period       Time period (last-week, last-month, last-quarter, or YYYY-MM-DD-to-YYYY-MM-DD)
--since-last-run        Generate from the date of the last entry in the existing release notes file
--template-dir          Template directory (default: templates)
--output-file           Output file (default: release-notes.md)
--release-notes-dir     Directory to store individual release notes (default: release_notes)
--only-new-releases     Only process and send to Slack releases that haven't been saved before
--use-ai                Use AI to generate descriptions
--slack-enabled         Enable Slack notifications
-v, --verbose           Enable verbose logging
```

### Environment Variables

The following environment variables are used:

- `GITHUB_TOKEN` - GitHub API token (required)
- `AI_API_KEY` - OpenAI API key (required for AI descriptions)
- `SLACK_WEBHOOK_URL` - Slack webhook URL (required for Slack notifications)

### GitHub Actions

The included GitHub Actions workflow allows you to:

1. Generate release notes automatically on a schedule (1st of each month)
2. Trigger generation manually with custom parameters
3. Commit the release notes directly to the repository
4. Optionally send to Slack

To set up:

1. Add the repository secrets in your GitHub repository:
   - `GITHUB_TOKEN` (automatically provided)
   - `AI_API_KEY` (for AI-powered descriptions)
   - `SLACK_WEBHOOK_URL` (for Slack notifications)

2. The workflow can be triggered:
   - Manually from the Actions tab
   - Automatically on the 1st of each month

## AI-Powered Descriptions

When enabled, the tool uses OpenAI to generate concise summaries of changes between tags, including:

1. A high-level summary of changes
2. Key improvements or features added
3. Potential breaking changes

To enable:

1. Set the `--use-ai` flag when running the tool
2. Provide a valid OpenAI API key via the `AI_API_KEY` environment variable

## Slack Integration

Share release notes with your team via Slack:

1. Set the `--slack-enabled` flag when running the tool
2. Provide a webhook URL via the `SLACK_WEBHOOK_URL` environment variable

## Since Last Run Feature

The `--since-last-run` option automatically detects the date of the last entry in the existing release notes file and generates new entries from that date forward. This is useful for:

1. Incremental updates without manually specifying dates
2. Ensuring no releases are missed between runs
3. Automated regular updates via GitHub Actions

## Customizing Output

Customize the output by editing the template in the `templates` directory. The main template is `release-notes.md.j2`, which uses the Jinja2 format.

## Example Output

The output file will be structured chronologically, with newest changes at the top:

## Individual Component Release Notes

The tool can generate separate release notes files for each component release:

1. Each component release is saved as a separate file in the `release_notes` directory (or the directory specified with `--release-notes-dir`)
2. Files are named in the format `YYYY-MM-DD_component-name_tag.md`
3. This allows for better organization and tracking of releases by component

This feature helps with:
- Tracking which releases have already been processed
- Creating a structured archive of all component releases
- Simplifying the process of notifying about new releases

## New Releases Notification

The `--only-new-releases` flag enables a mode where:

1. The tool checks if a release has already been processed (by looking for its file in the release notes directory)
2. Only new releases that haven't been processed before are sent to Slack
3. This prevents duplicate notifications and ensures team members only see fresh updates

When this mode is enabled with Slack integration:
- Only newly discovered releases trigger notifications
- The Slack message is formatted to highlight what's new since the last run
- Each component's changes are summarized in a readable format

Here's an example Slack message when using `--only-new-releases`:

```
*New Release Notes for last-month*

*keboola.component-name* 1.2.3 - 2023-09-15:
_This release improves performance by optimizing the data processing pipeline and fixing several edge cases..._
• Fix data processing for large files
• Improve error handling
• Update dependencies
<https://github.com/keboola/component-name/releases/tag/1.2.3|View on GitHub>

*another.component* 2.0.0 - 2023-09-14:
_Major version update with breaking changes to the configuration format..._
• Add support for new API v2
• Refactor configuration structure
• Improve logging
<https://github.com/keboola/another-component/releases/tag/2.0.0|View on GitHub>
``` 