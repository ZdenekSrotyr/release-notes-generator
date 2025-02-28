#!/usr/bin/env python3
import datetime
import re
from github import Github
from src.config import GITHUB_ORGANIZATION, REPO_PATTERNS, logger


def initialize_github_client(token):
    """Initialize GitHub client with the provided token."""
    try:
        github = Github(token)
        return github
    except Exception as e:
        logger.error(f"Error initializing GitHub client: {e}")
        raise


def get_repositories(github, organization=GITHUB_ORGANIZATION, patterns=REPO_PATTERNS):
    """Get list of repositories based on pattern."""
    logger.info("Finding repositories...")
    repos = []

    # Get repos by pattern
    for pattern in patterns.split(','):
        query = f"org:{organization} {pattern} in:name"
        try:
            search_results = github.search_repositories(query=query)
            for repo in search_results:
                repos.append(repo)
        except Exception as e:
            logger.error(f"Error searching for repositories with pattern '{pattern}': {e}")

    logger.info(f"Found {len(repos)} repositories to process")
    return repos


def fix_timezone(date):
    """Ensure date has timezone information."""
    if date.tzinfo is None:
        return date.replace(tzinfo=datetime.timezone.utc)
    return date


def get_repo_tags(repo, max_count=50):
    """Get the most recent tags for a repository (limited to max_count)."""
    logger.info(f"Fetching {max_count} most recent tags for {repo.name}")

    all_tags = []
    tag_count = 0

    try:
        for tag in repo.get_tags():
            try:
                # Get tag commit date
                commit_date = fix_timezone(tag.commit.commit.author.date)

                # Create tag object with all necessary information
                tag_obj = {
                    'name': tag.name,
                    'commit': tag.commit.sha,
                    'date': commit_date,
                    'message': tag.commit.commit.message,
                    'url': tag.commit.html_url
                }

                all_tags.append(tag_obj)
                tag_count += 1

                # Limit to max_count tags for performance
                if tag_count >= max_count:
                    logger.info(f"Retrieved {max_count} tags for {repo.name}")
                    break

            except Exception as e:
                logger.warning(f"Error processing tag {tag.name} in {repo.name}: {e}")

    except Exception as e:
        logger.error(f"Error getting tags for {repo.name}: {e}")

    # Sort tags by date (newest first)
    all_tags.sort(key=lambda x: x['date'], reverse=True)

    logger.info(f"Fetched {len(all_tags)} tags for {repo.name}")
    return all_tags


def get_tags_in_period(repo, start_date, end_date):
    """Get tags created within a specified time period, filtered by semantic versioning."""
    logger.info(
        f"Finding tags for {repo.name} between {start_date.strftime('%Y-%m-%d')} and {end_date.strftime('%Y-%m-%d')}")

    # Make sure dates have timezone information
    start_date = fix_timezone(start_date)
    end_date = fix_timezone(end_date)

    # Regex for matching semantic versions (e.g. 1.2.3)
    semver_pattern = re.compile(r'^v?\d+\.\d+\.\d+(-.*)?$')

    # Get recent tags without caching (default: 50 tags)
    all_tags = get_repo_tags(repo)

    # Filter tags by date and semantic versioning
    tags_in_period = []

    for tag in all_tags:
        # Skip if tag doesn't match semantic versioning
        if not semver_pattern.match(tag['name']):
            continue

        # Check if the tag is within our date range
        if start_date <= tag['date'] <= end_date:
            tags_in_period.append(tag)

    logger.info(f"Found {len(tags_in_period)} tags in period for {repo.name}")
    return tags_in_period


def get_changes_between_tags(repo, previous_tag, current_tag):
    """Get changes between two tags."""
    logger.info(f"Getting changes between {previous_tag['name']} and {current_tag['name']} in {repo.name}")

    # Initialize result
    result = {
        'changes': [],
        'ai_description': None
    }

    try:
        # Get comparison between tags
        comparison = repo.compare(previous_tag['commit'], current_tag['commit'])

        # Get commits
        commits = comparison.commits

        # Process each commit
        for commit in commits:
            # Check if commit is a pull request merge
            pr_number = None
            pr_title = None
            pr_body = None

            # Look for PR reference in commit message
            merge_match = re.search(r'Merge pull request #(\d+)', commit.commit.message)
            if merge_match:
                pr_number = merge_match.group(1)

                # Try to get the full PR information
                try:
                    pr = repo.get_pull(int(pr_number))
                    pr_title = pr.title
                    pr_body = pr.body
                except Exception as e:
                    logger.warning(f"Could not fetch PR #{pr_number} details: {e}")
                    # Fallback to extracting from commit message
                    message_lines = commit.commit.message.strip().split('\n')
                    if len(message_lines) > 1:
                        pr_title = message_lines[1].strip()
                        # Extract the rest as body if available
                        if len(message_lines) > 2:
                            pr_body = '\n'.join(message_lines[2:]).strip()

            # Create change entry
            change = {
                'commit_sha': commit.sha,
                'commit_url': commit.html_url,
                'commit_message': commit.commit.message,
                'author': commit.commit.author.name,
                'date': fix_timezone(commit.commit.author.date)
            }

            # Add PR info if available
            if pr_number:
                change['pr_number'] = pr_number
                change['pr_url'] = f"https://github.com/{repo.full_name}/pull/{pr_number}"
                change['title'] = pr_title if pr_title else f"PR #{pr_number}"
                if pr_body:
                    change['pr_body'] = pr_body
            else:
                change['title'] = commit.commit.message.split('\n')[0]

            # Add to changes list
            result['changes'].append(change)

        # Remove duplicates (sometimes the same PR can appear twice)
        unique_changes = []
        seen_prs = set()

        for change in result['changes']:
            # If it's a PR and we've seen it, skip
            if 'pr_number' in change and change['pr_number'] in seen_prs:
                continue

            # If it's a PR, mark as seen
            if 'pr_number' in change:
                seen_prs.add(change['pr_number'])

            # Add to unique changes
            unique_changes.append(change)

        result['changes'] = unique_changes

    except Exception as e:
        logger.error(f"Error getting changes between tags: {e}")

    return result
