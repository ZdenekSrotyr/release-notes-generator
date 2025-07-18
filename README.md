# Release Notes Generator

A Keboola Custom Python Component that generates release notes from GitHub repositories using AI-powered summaries.

## Features

- **GitHub Integration**: Fetches release data from GitHub repositories using optimized GraphQL API
- **AI Summaries**: Generates intelligent summaries of changes using Google's Gemini AI
- **Keboola Integration**: Native Keboola component with table output and state management
- **Parallel Processing**: Efficient parallel processing of multiple repositories
- **Ultra-Optimized GraphQL**: Single GraphQL request for all repositories (50 per batch) for maximum performance

## Performance

This component uses ultra-optimized GraphQL queries that:
- Fetch all repository data in batches of 50 repositories per request
- Include tags, workflow files, and package.json content in a single query
- Reduce API calls by 90% compared to standard GitHub API
- Process 170+ repositories in just a few API requests

## Configuration

### Required Parameters

- `github_token` or `#github_token`: GitHub API token with repository access

### Optional Parameters

- `google_ai_api_key` or `#google_ai_api_key`: Google AI API key for generating summaries
- `days_back`: Number of days to look back (default: 30)
- `table_name`: Output table name (default: "releases")

### Example Configuration

```json
{
  "parameters": {
    "github_token": "your_github_token",
    "google_ai_api_key": "your_google_ai_key",
    "days_back": 30,
    "table_name": "releases"
  }
}
```

## Installation

1. Clone this repository
2. Install dependencies using UV: `uv sync`
3. Set up your configuration in `data/config.json`
4. Run: `python main.py`

## Local Development

For local testing, create a `data/` directory with your configuration:

```
data/
├── config.json
└── out/
    └── tables/
```

Example `data/config.json`:
```json
{
  "parameters": {
    "github_token": "your_github_token",
    "google_ai_api_key": "your_google_ai_key",
    "days_back": 30,
    "table_name": "releases"
  }
}
```

## Output

The component generates a table with the following columns:

- `date`: Release date
- `repo_name`: Repository name
- `component_name`: Component identifier
- `tag_name`: Git tag name
- `changes`: JSON array of changes
- `ai_description`: AI-generated summary (if available)
- `component_stage`: Component stage (private/beta/production)
- `tag_url`: Link to GitHub release

## Recent Updates

- **Removed Docker support** - Component runs locally with UV package manager
- **Simplified configuration** - Removed complex GraphQL optimization parameters
- **Always uses ultra-optimized GraphQL** - Maximum performance by default
- **Batch processing** - Processes all repositories in batches of 50
- **Improved error handling** - Graceful handling of missing AI API keys

## Troubleshooting

### Rate Limiting
If you encounter GitHub rate limiting:
- Use a GitHub token with higher rate limits
- The component automatically uses optimized GraphQL to minimize API calls

### AI Summaries Not Working
- Ensure Google AI API key is provided
- Check API key permissions
- Verify internet connectivity
- Component will still generate release notes without AI summaries

### Missing Component Names
- Ensure repositories have proper workflow files (`.github/workflows/*.yml`)
- Check for `package.json` with component ID
- Verify GitHub token has repository access

## License

MIT License - see LICENSE file for details. 