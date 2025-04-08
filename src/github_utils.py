#!/usr/bin/env python3
import datetime
import re
import time
from github import Github
from src.config import GITHUB_ORGANIZATION, REPO_PATTERNS, logger


def initialize_github_client(token):
    """Initialize GitHub client with the provided token."""
    try:
        # Add retry mechanism with exponential backoff
        github = Github(
            token,
            retry=3,  # Number of retries
            per_page=100,  # Maximum items per page
            timeout=30  # Timeout in seconds
        )
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
        # Use pagination to handle rate limits better
        for tag in repo.get_tags().get_page(0):
            try:
                # Get both commit date and tag creation date
                commit_date = fix_timezone(tag.commit.commit.author.date)
                tag_date = fix_timezone(tag.commit.commit.committer.date)

                # Create tag object with all necessary information
                tag_obj = {
                    'name': tag.name,
                    'commit': tag.commit.sha,
                    'date': max(commit_date, tag_date),  # Use the later date
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
                # If we hit rate limit, wait and retry
                if "API rate limit exceeded" in str(e):
                    logger.info("Rate limit hit, waiting 60 seconds...")
                    time.sleep(60)
                    continue

    except Exception as e:
        logger.error(f"Error getting tags for {repo.name}: {e}")
        # If we hit rate limit, wait and retry
        if "API rate limit exceeded" in str(e):
            logger.info("Rate limit hit, waiting 60 seconds...")
            time.sleep(60)
            return get_repo_tags(repo, max_count)  # Retry the whole function

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

    # Get recent tags without caching (increased to 100 tags)
    all_tags = get_repo_tags(repo, max_count=100)

    # Filter tags by date and semantic versioning
    filtered_tags = []
    for tag in all_tags:
        # Check if tag is within the date range
        if start_date <= tag['date'] <= end_date:
            # Check if tag follows semantic versioning
            if semver_pattern.match(tag['name']):
                filtered_tags.append(tag)
            else:
                logger.debug(f"Skipping non-semantic version tag: {tag['name']}")

    # Sort tags by date (newest first)
    filtered_tags.sort(key=lambda x: x['date'], reverse=True)

    # Verify that tags have changes between them
    valid_tags = []
    for i in range(len(filtered_tags)):
        current_tag = filtered_tags[i]
        if i < len(filtered_tags) - 1:
            previous_tag = filtered_tags[i + 1]
            try:
                # Check if there are any changes between tags
                changes = get_changes_between_tags(repo, previous_tag['name'], current_tag['name'])
                if changes:
                    valid_tags.append(current_tag)
                    logger.info(f"Found valid tag {current_tag['name']} with changes")
                else:
                    logger.info(f"Skipping tag {current_tag['name']} - no changes found")
            except Exception as e:
                logger.warning(f"Error checking changes for tag {current_tag['name']}: {e}")
        else:
            valid_tags.append(current_tag)

    logger.info(f"Found {len(valid_tags)} valid tags for {repo.name}")
    return valid_tags


def get_changes_between_tags(repo, previous_tag, current_tag):
    """Get changes between two tags."""
    logger.info(f"Getting changes between {previous_tag} and {current_tag} in {repo.name}")

    try:
        # Add delay between API calls to avoid rate limits
        time.sleep(1)  # 1 second delay between calls

        comparison = repo.compare(previous_tag, current_tag)
        commits = comparison.commits

        # Process commits in batches to avoid rate limits
        batch_size = 10
        changes = []
        for i in range(0, len(commits), batch_size):
            batch = commits[i:i + batch_size]
            for commit in batch:
                # Extract PR number and title from commit message
                pr_match = re.search(r'Merge pull request #(\d+)', commit.commit.message)
                if pr_match:
                    pr_number = pr_match.group(1)
                    pr_title = commit.commit.message.split('\n')[1] if len(commit.commit.message.split('\n')) > 1 else f"PR #{pr_number}"
                    changes.append({
                        'title': pr_title,
                        'pr_number': pr_number,
                        'pr_url': f"https://github.com/{repo.full_name}/pull/{pr_number}",
                        'commit_sha': commit.sha,
                        'commit_url': commit.html_url,
                        'author': commit.commit.author.name,
                        'date': fix_timezone(commit.commit.author.date)
                    })
            # Add delay between batches
            if i + batch_size < len(commits):
                time.sleep(1)

        return changes

    except Exception as e:
        logger.error(f"Error getting changes between tags: {e}")
        # If we hit rate limit, wait and retry
        if "API rate limit exceeded" in str(e):
            logger.info("Rate limit hit, waiting 60 seconds...")
            time.sleep(60)
            return get_changes_between_tags(repo, previous_tag, current_tag)  # Retry the whole function
        return []