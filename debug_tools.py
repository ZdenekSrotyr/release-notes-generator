#!/usr/bin/env python3
import os
import sys
import yaml
import argparse
import datetime
import logging
from github import Github

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('release-notes-debug')

def load_config(config_file):
    """Load configuration from file."""
    try:
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)
            logger.info(f"Configuration loaded successfully from {config_file}")
            return config
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        raise

def get_github_client(config):
    """Initialize GitHub client from config."""
    github_token = config.get('github_token') or os.environ.get('GITHUB_TOKEN')
    if not github_token:
        logger.error("GitHub token is missing")
        raise ValueError("GitHub token is required. Set it in config or GITHUB_TOKEN env variable.")
    else:
        logger.info("GitHub token found")
    
    return Github(github_token)

def analyze_repository_tags(config, repo_name):
    """Analyze tags in a repository and show their chronological order."""
    logger.info(f"Analyzing tags for repository: {repo_name}")
    
    github = get_github_client(config)
    organization = config.get('organization', '')
    
    # Check if repo_name includes organization
    if '/' in repo_name:
        full_repo_name = repo_name
    else:
        if not organization:
            logger.error("Organization not specified in config and not included in repo name")
            return
        full_repo_name = f"{organization}/{repo_name}"
    
    logger.info(f"Fetching repository: {full_repo_name}")
    try:
        repo = github.get_repo(full_repo_name)
        logger.info(f"Repository found: {repo.full_name}")
        
        # Get all tags
        logger.info("Fetching all tags...")
        all_tags = list(repo.get_tags())
        logger.info(f"Found {len(all_tags)} tags in repository")
        
        # Get tag dates and sort chronologically
        tags_with_dates = []
        for tag in all_tags:
            try:
                commit = tag.commit
                commit_date = commit.commit.author.date
                if commit_date.tzinfo is None:
                    commit_date = commit_date.replace(tzinfo=datetime.timezone.utc)
                
                tags_with_dates.append({
                    'name': tag.name,
                    'date': commit_date,
                    'commit': commit.sha,
                    'message': commit.commit.message,
                    'url': commit.html_url
                })
            except Exception as e:
                logger.warning(f"Error processing tag {tag.name}: {e}")
        
        # Sort by date
        tags_with_dates.sort(key=lambda x: x['date'])
        
        # Print chronological order
        print("\nTags in chronological order (oldest first):")
        print("=" * 80)
        print(f"{'#':<4} {'Tag Name':<20} {'Date':<22} {'Commit':<10} {'Message'}")
        print("-" * 80)
        
        for i, tag in enumerate(tags_with_dates):
            print(f"{i+1:<4} {tag['name']:<20} {tag['date'].strftime('%Y-%m-%d %H:%M:%S'):<22} {tag['commit'][:7]:<10} {tag['message'].split(chr(10))[0][:40]}")
        
        print("\nPotential comparison issues:")
        print("=" * 80)
        
        # Check for version ordering issues
        for i in range(len(tags_with_dates) - 1):
            current = tags_with_dates[i]
            next_tag = tags_with_dates[i + 1]
            
            # Simple semantic versioning check for common issues
            try:
                current_parts = current['name'].split('.')
                next_parts = next_tag['name'].split('.')
                
                if len(current_parts) >= 3 and len(next_parts) >= 3:
                    # Check if version numbers suggest a different order than dates
                    try:
                        current_version = tuple(map(int, current_parts))
                        next_version = tuple(map(int, next_parts))
                        
                        if current_version > next_version and current['date'] < next_tag['date']:
                            print(f"Version ordering issue: {current['name']} (older date) has higher version than {next_tag['name']} (newer date)")
                    except:
                        # Not all parts can be converted to int, skip comparison
                        pass
            except:
                pass
            
            # Check for tags created very close together
            time_diff = (next_tag['date'] - current['date']).total_seconds()
            if time_diff < 60:  # less than 1 minute apart
                print(f"Very close tags: {current['name']} and {next_tag['name']} created only {time_diff:.1f} seconds apart")
        
        # Show some example comparisons for debugging
        print("\nSample comparison URLs for adjacent tags:")
        print("=" * 80)
        for i in range(min(5, len(tags_with_dates) - 1)):
            current = tags_with_dates[i]
            next_tag = tags_with_dates[i + 1]
            print(f"{current['name']} → {next_tag['name']}: https://github.com/{repo.full_name}/compare/{current['name']}...{next_tag['name']}")
        
    except Exception as e:
        logger.error(f"Error analyzing repository {repo_name}: {e}")

def main():
    parser = argparse.ArgumentParser(description='Debug tools for release notes generator')
    parser.add_argument('-c', '--config', default='config.yml', help='Path to config file')
    parser.add_argument('-r', '--repo', required=True, help='Repository name to analyze')
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose logging')
    args = parser.parse_args()
    
    if args.verbose:
        logger.setLevel(logging.DEBUG)
        logger.debug("Verbose logging enabled")
    
    try:
        config = load_config(args.config)
        analyze_repository_tags(config, args.repo)
    except Exception as e:
        logger.critical(f"Unhandled exception: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 