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

# Full options example
python main.py -o keboola -t last-month -r my-component --since-last-run --use-ai --slack-enabled -v
```

### All Command Line Arguments

```
-o, --organization     GitHub organization (default: keboola)
-r, --repo             Generate for a single repository
-p, --repo-patterns    Repository search patterns (comma separated, default: component)
--repos                Explicitly listed repositories (comma separated)
-t, --time-period      Time period (last-week, last-month, last-quarter, or YYYY-MM-DD-to-YYYY-MM-DD)
--since-last-run       Generate from the date of the last entry in the existing release notes file
--template-dir         Template directory (default: templates)
--output-file          Output file (default: release-notes.md)
--use-ai               Use AI to generate descriptions
--slack-enabled        Enable Slack notifications
-v, --verbose          Enable verbose logging
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

```markdown
# Release Notes

_Generated on 2023-08-31 15:30:45_

Period: last-month

## Summary of Changes

### 2023-08-30 - keboola.ex-component 1.2.3

**Component:** [keboola.ex-component](https://github.com/keboola/keboola-component-example)  
**Tag:** [1.2.3](https://github.com/keboola/keboola-component-example/releases/tag/1.2.3)  

#### AI Summary
This release focuses on performance improvements and bug fixes. The main changes include optimized file processing for large files and improved data download efficiency. No breaking changes were introduced.

#### Changes:
- Fix bug in large file processing ([#123](https://github.com/keboola/keboola-component-example/pull/123))
- Improve performance of data downloads ([#124](https://github.com/keboola/keboola-component-example/pull/124))

### 2023-08-28 - keboola.other-component 2.0.0

**Component:** [keboola.other-component](https://github.com/keboola/keboola-component-other)  
**Tag:** [2.0.0](https://github.com/keboola/keboola-component-other/releases/tag/2.0.0)

#### AI Summary
This is a major release that introduces API v2 support. It maintains backward compatibility with previous versions but adds significant new functionality. The API handling code has been completely refactored for better performance and maintainability.

#### Changes:
- Add support for new API v2 ([#45](https://github.com/keboola/keboola-component-other/pull/45))
- Maintain backward compatibility with previous version ([#46](https://github.com/keboola/keboola-component-other/pull/46))
``` 