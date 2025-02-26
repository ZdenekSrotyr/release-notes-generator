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
- Flexible configuration via configuration file
- Customizable time period for generating release notes

## Installation

```bash
# Clone the repository
git clone https://github.com/your-org/release-notes-generator.git
cd release-notes-generator

# Install dependencies
pip install -r requirements.txt
```

## Configuration

Configure the tool by editing the `config.yml` file:

```yaml
# GitHub API Token - can be replaced with GITHUB_TOKEN environment variable
# github_token: "ghp_your_token_here"

# GitHub organization
organization: "keboola"

# Time period for release notes
# Options: last-week, last-month, last-quarter, or specific period (e.g. 2023-01-01-to-2023-02-01)
time_period: "last-month"

# Repository search patterns
repo_patterns:
  - "component"

# Explicitly listed repositories (optional)
repos:
  - "keboola-component-example"
  - "keboola-component-other"

# Template directory
template_dir: "templates"

# Output file
output_file: "release-notes.md"

# AI-powered description generation
use_ai: false
ai_provider: "openai"
# ai_api_key: "your_openai_api_key"
# AI_API_KEY environment variable can be used instead

# Slack integration
slack_enabled: false
# slack_webhook_url: "https://hooks.slack.com/services/xxx/yyy/zzz"
# SLACK_WEBHOOK_URL environment variable can be used instead
# slack_channel: "releases"
# slack_file_upload_token: "xoxb-your-slack-token"
```

## Usage

### Command Line

```bash
# Set GitHub token (if not in config.yml)
export GITHUB_TOKEN="ghp_your_token_here"

# Run the generator with default config file
python main.py

# Use a custom config file
python main.py -c custom-config.yml
```

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

1. Set `use_ai: true` in config.yml or provide the AI_API_KEY environment variable
2. Ensure you have a valid OpenAI API key

## Slack Integration

Share release notes with your team via Slack:

1. Set `slack_enabled: true` in config.yml
2. Provide a webhook URL in config or via the SLACK_WEBHOOK_URL environment variable
3. Optionally configure a specific channel and file upload token

## Customizing Output

Customize the output by editing the template in the `templates` directory. The main template is `release-notes.md.j2`, which uses the Jinja2 format.

## Adding Support for Other Departments

1. To add repositories from other departments, add them to the `repos` section in the config file.
2. If the repositories from another department share a common pattern in the name, add that pattern to the `repo_patterns` section.

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
**Previous Tag:** 1.2.2

#### AI Summary
This release focuses on performance improvements and bug fixes. The main changes include optimized file processing for large files and improved data download efficiency. No breaking changes were introduced.

#### Changes:
- Fix bug in large file processing ([#123](https://github.com/keboola/keboola-component-example/pull/123))
- Improve performance of data downloads ([#124](https://github.com/keboola/keboola-component-example/pull/124))

#### Files Changed:
- 5 files modified
- 2 added
- 3 modified
- 0 removed

### 2023-08-28 - keboola.other-component 2.0.0

**Component:** [keboola.other-component](https://github.com/keboola/keboola-component-other)  
**Tag:** [2.0.0](https://github.com/keboola/keboola-component-other/releases/tag/2.0.0)  
**Previous Tag:** 1.5.2

#### AI Summary
This is a major release that introduces API v2 support. It maintains backward compatibility with previous versions but adds significant new functionality. The API handling code has been completely refactored for better performance and maintainability.

#### Changes:
- Add support for new API v2 ([#45](https://github.com/keboola/keboola-component-other/pull/45))
- Maintain backward compatibility with previous version ([#46](https://github.com/keboola/keboola-component-other/pull/46))

#### Files Changed:
- 12 files modified
- 5 added
- 7 modified
- 0 removed
``` 