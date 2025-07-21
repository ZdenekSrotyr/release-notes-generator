#!/usr/bin/env python3
"""
GraphQL-based GitHub utilities for faster API access.
This module provides the same interface as github_utils.py but uses GraphQL API.
"""
import datetime
import re
import traceback
import json
import yaml
from typing import List, Dict, Any, Optional
import requests
from src.config import GITHUB_ORGANIZATION, REPO_PATTERNS, logger


class GraphQLRepoWrapper:
    """Wrapper class to make GraphQL repo data compatible with PyGithub repo objects."""
    
    def __init__(self, repo_data: dict, github_client: dict):
        self._data = repo_data
        self._github_client_data = github_client
        
        # Pre-fetched data
        self._tags = repo_data.get('_tags', [])
        self._workflow_files = repo_data.get('_workflow_files', [])
        self._package_json = repo_data.get('_package_json')
    
    @property
    def name(self):
        return self._data['name']
    
    @property
    def full_name(self):
        return self._data['full_name']
    
    @property
    def url(self):
        return self._data['url']
    
    @property
    def default_branch(self):
        return self._data['default_branch']
    
    @property
    def _github_client(self):
        return self._github_client_data
    
    def get_tags(self):
        """Return tags in PyGithub format."""
        return self._tags
    
    def get_commits(self, sha=None):
        """Mock method for compatibility - not implemented in GraphQL version."""
        raise NotImplementedError("get_commits not implemented in GraphQL version")
    
    def compare(self, base, head):
        """Compare two commits using GraphQL."""
        logger.info(f"Comparing commits {base} and {head} for {self.name}")
        try:
            # GraphQL query to get commits between two SHAs
            # We need to get the commit dates first, then use history with timestamps
            query = """
            query($owner: String!, $name: String!, $base: String!, $head: String!) {
                repository(owner: $owner, name: $name) {
                    baseCommit: object(expression: $base) {
                        ... on Commit {
                            committedDate
                        }
                    }
                    headCommit: object(expression: $head) {
                        ... on Commit {
                            committedDate
                            history(first: 100) {
                                nodes {
                                    oid
                                    message
                                    url
                                    author {
                                        name
                                        date
                                    }
                                    committedDate
                                }
                            }
                        }
                    }
                }
            }
            """
            
            variables = {
                "owner": GITHUB_ORGANIZATION,
                "name": self.name,
                "base": base,
                "head": head
            }
            
            response = requests.post(
                self._github_client_data["url"], 
                json={"query": query, "variables": variables}, 
                headers=self._github_client_data["headers"]
            )
            
            if response.status_code != 200:
                logger.error(f"GraphQL API error: {response.status_code} - {response.text}")
                return None
                
            data = response.json()
            if "errors" in data:
                logger.error(f"GraphQL errors: {data['errors']}")
                return None
            
            repo_data = data["data"]["repository"]
            if not repo_data or not repo_data["baseCommit"] or not repo_data["headCommit"]:
                logger.error(f"Repository or commit not found")
                return None
            
            # Get base commit date
            base_commit = repo_data["baseCommit"]
            if not base_commit:
                logger.error(f"Base commit not found")
                return None
            
            # Get head commit and its history
            head_commit = repo_data["headCommit"]
            if not head_commit or not head_commit["history"]:
                logger.error(f"Head commit or history not found")
                return None
            
            # Extract commits from history and filter by date
            commits_data = head_commit["history"]["nodes"]
            commits = []
            
            base_date = datetime.datetime.fromisoformat(base_commit["committedDate"].replace('Z', '+00:00'))
            
            for commit_data in commits_data:
                commit_date = datetime.datetime.fromisoformat(commit_data["committedDate"].replace('Z', '+00:00'))
                
                # Only include commits that are newer than the base commit
                if commit_date > base_date:
                    commit = {
                        'sha': commit_data["oid"],
                        'message': commit_data["message"],
                        'url': commit_data["url"],
                        'author': {
                            'name': commit_data["author"]["name"] if commit_data["author"] else "Unknown",
                            'date': commit_data["author"]["date"] if commit_data["author"] else None
                        }
                    }
                    commits.append(commit)
            
            # Create a mock comparison object similar to PyGithub
            class MockComparison:
                def __init__(self, commits):
                    self.commits = commits
                
                def __iter__(self):
                    return iter(self.commits)
                
                def __len__(self):
                    return len(self.commits)
            
            logger.info(f"Found {len(commits)} commits between {base} and {head} for {self.name}")
            return MockComparison(commits)
            
        except Exception as e:
            logger.error(f"Error in GraphQL compare: {e}")
            return None


def initialize_github_client(token):
    """Initialize GitHub GraphQL client with the provided token."""
    try:
        # GraphQL endpoint
        url = "https://api.github.com/graphql"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        
        # Test the connection
        test_query = """
        query {
            viewer {
                login
            }
        }
        """
        
        response = requests.post(url, json={"query": test_query}, headers=headers)
        if response.status_code != 200:
            raise Exception(f"GraphQL API error: {response.status_code} - {response.text}")
        
        logger.info("GitHub GraphQL client initialized successfully")
        return {"url": url, "headers": headers, "token": token}
        
    except Exception as e:
        logger.error(f"Error initializing GitHub GraphQL client: {e}")
        logger.error(f"GitHub GraphQL client traceback:")
        logger.error(traceback.format_exc())
        raise


def get_repositories_with_full_data(github, organization=GITHUB_ORGANIZATION, patterns=REPO_PATTERNS, max_tags_per_repo=10):
    """
    Get repositories with all their data in a single GraphQL request per repository.
    This is the optimized version that minimizes API calls.
    """
    logger.info("Finding repositories with full data using optimized GraphQL...")
    repos = []

    try:
        # First, get list of repositories
        repos_query = """
        query($org: String!, $first: Int!, $after: String) {
            organization(login: $org) {
                repositories(first: $first, after: $after) {
                    nodes {
                        name
                        nameWithOwner
                        url
                        defaultBranchRef {
                            name
                        }
                    }
                    pageInfo {
                        hasNextPage
                        endCursor
                    }
                }
            }
        }
        """
        
        variables = {
            "org": organization,
            "first": 100,
            "after": None
        }
        
        # Get all repositories (handle pagination)
        all_repo_names = []
        has_next_page = True
        while has_next_page:
            response = requests.post(
                github["url"], 
                json={"query": repos_query, "variables": variables}, 
                headers=github["headers"]
            )
            
            if response.status_code != 200:
                logger.error(f"GraphQL API error: {response.status_code} - {response.text}")
                break
                
            data = response.json()
            if "errors" in data:
                logger.error(f"GraphQL errors: {data['errors']}")
                break
                
            org_data = data["data"]["organization"]
            if not org_data:
                logger.error(f"Organization {organization} not found")
                break
                
            # Filter repositories by pattern
            for repo in org_data["repositories"]["nodes"]:
                repo_name = repo["name"]
                
                # Check if repo name matches any pattern
                matches_pattern = False
                for pattern in patterns.split(','):
                    if pattern.strip().lower() in repo_name.lower():
                        matches_pattern = True
                        break
                
                if matches_pattern:
                    all_repo_names.append({
                        "name": repo["name"],
                        "full_name": repo["nameWithOwner"],
                        "url": repo["url"],
                        "default_branch": repo["defaultBranchRef"]["name"] if repo["defaultBranchRef"] else "main"
                    })
            
            # Handle pagination
            page_info = org_data["repositories"]["pageInfo"]
            has_next_page = page_info["hasNextPage"]
            if has_next_page:
                variables["after"] = page_info["endCursor"]
        
        logger.info(f"Found {len(all_repo_names)} repositories matching pattern '{patterns}'")
        
        # Now get full data for each repository in a single request
        for repo_info in all_repo_names:
            try:
                # Comprehensive GraphQL query to get all data for one repository
                # This includes tags, workflow files content, and package.json in one request
                full_data_query = """
                query($owner: String!, $name: String!, $maxTags: Int!) {
                    repository(owner: $owner, name: $name) {
                        name
                        nameWithOwner
                        url
                        defaultBranchRef {
                            name
                        }
                        # Get recent tags
                        refs(first: $maxTags, refPrefix: "refs/tags/", orderBy: {field: TAG_COMMIT_DATE, direction: DESC}) {
                            nodes {
                                name
                                target {
                                    ... on Commit {
                                        oid
                                        committedDate
                                        message
                                        url
                                    }
                                }
                            }
                        }
                        # Get workflow files content directly
                        workflows: object(expression: "HEAD:.github/workflows") {
                            ... on Tree {
                                entries {
                                    name
                                    type
                                    object {
                                        ... on Blob {
                                            text
                                        }
                                    }
                                }
                            }
                        }
                        # Get package.json content
                        packageJson: object(expression: "HEAD:package.json") {
                            ... on Blob {
                                text
                            }
                        }
                    }
                }
                """
                
                variables = {
                    "owner": organization,
                    "name": repo_info["name"],
                    "maxTags": max_tags_per_repo
                }
                
                response = requests.post(
                    github["url"], 
                    json={"query": full_data_query, "variables": variables}, 
                    headers=github["headers"]
                )
                
                if response.status_code != 200:
                    logger.warning(f"Could not get full data for {repo_info['name']}: {response.status_code}")
                    # Add basic repo info anyway
                    repo_data = {
                        **repo_info,
                        "_github_client": github,
                        "_tags": [],
                        "_workflow_files": [],
                        "_package_json": None
                    }
                    repos.append(GraphQLRepoWrapper(repo_data, github))
                    continue
                    
                data = response.json()
                if "errors" in data:
                    logger.warning(f"GraphQL errors for {repo_info['name']}: {data['errors']}")
                    # Add basic repo info anyway
                    repo_data = {
                        **repo_info,
                        "_github_client": github,
                        "_tags": [],
                        "_workflow_files": [],
                        "_package_json": None
                    }
                    repos.append(GraphQLRepoWrapper(repo_data, github))
                    continue
                
                repo_data = data["data"]["repository"]
                if not repo_data:
                    logger.warning(f"Repository {repo_info['name']} not found")
                    continue
                
                # Process tags
                tags = []
                if repo_data["refs"]:
                    for ref in repo_data["refs"]["nodes"]:
                        if ref["target"]:
                            commit = ref["target"]
                            commit_date = datetime.datetime.fromisoformat(commit["committedDate"].replace('Z', '+00:00'))
                            
                            tag_obj = {
                                'name': ref["name"],
                                'commit': commit["oid"],
                                'date': fix_timezone(commit_date),
                                'message': commit["message"],
                                'url': commit["url"]
                            }
                            tags.append(tag_obj)
                
                # Process workflow files content
                workflow_files = []
                if repo_data.get("workflows") and repo_data["workflows"].get("entries"):
                    for entry in repo_data["workflows"]["entries"]:
                        if entry["type"] == "blob" and entry["name"].endswith(('.yml', '.yaml')):
                            if entry.get("object") and entry["object"].get("text"):
                                workflow_files.append({
                                    "path": f".github/workflows/{entry['name']}",
                                    "content": entry["object"]["text"]
                                })
                
                # Process package.json
                package_json = None
                if repo_data["packageJson"] and repo_data["packageJson"]["text"]:
                    package_json = repo_data["packageJson"]["text"]
                
                # Create complete repo object
                repo_data = {
                    **repo_info,
                    "_github_client": github,
                    "_tags": tags,
                    "_workflow_files": workflow_files,
                    "_package_json": package_json
                }
                
                repos.append(GraphQLRepoWrapper(repo_data, github))
                logger.info(f"Processed {repo_info['name']} with {len(tags)} tags, {len(workflow_files)} workflow files")
                
            except Exception as e:
                logger.error(f"Error processing repository {repo_info['name']}: {e}")
                # Add basic repo info anyway
                repo_data = {
                    **repo_info,
                    "_github_client": github,
                    "_tags": [],
                    "_workflow_files": [],
                    "_package_json": None
                }
                repos.append(GraphQLRepoWrapper(repo_data, github))
        
        logger.info(f"Successfully processed {len(repos)} repositories with full data")
        return repos
        
    except Exception as e:
        logger.error(f"Error getting repositories with full data: {e}")
        logger.error(f"GraphQL full data traceback:")
        logger.error(traceback.format_exc())
        return []


def get_all_repositories_data_in_single_request(github_client: dict, organization: str) -> List[GraphQLRepoWrapper]:
    """
    Get all repositories data using ultra-optimized single GraphQL request.
    Processes repositories in batches of 50 to handle all repositories.
    """
    logger.info("Finding repositories with ultra-optimized single GraphQL request...")
    
    # First, get all repository names as dictionaries
    all_repos_raw = get_repositories(github_client, organization)
    logger.info(f"Found {len(all_repos_raw)} repositories matching pattern 'component'")
    
    # Convert to list of dictionaries for processing
    all_repos = []
    for repo in all_repos_raw:
        if hasattr(repo, 'name'):
            all_repos.append({
                'name': repo.name,
                'full_name': getattr(repo, 'full_name', repo.name),
                'url': getattr(repo, 'url', ''),
                'default_branch': getattr(repo, 'default_branch', 'main')
            })
        else:
            # If it's already a dict
            all_repos.append(repo)
    
    all_processed_repos = []
    
    # Process repositories in batches of 50
    batch_size = 50
    total_batches = (len(all_repos) + batch_size - 1) // batch_size
    
    for batch_num in range(total_batches):
        start_idx = batch_num * batch_size
        end_idx = min(start_idx + batch_size, len(all_repos))
        batch_repos = all_repos[start_idx:end_idx]
        
        logger.info(f"Processing batch {batch_num + 1}/{total_batches} (repositories {start_idx + 1}-{end_idx})")
        
        # Process this batch
        batch_processed_repos = _process_repository_batch(github_client, batch_repos)
        all_processed_repos.extend(batch_processed_repos)
        
        logger.info(f"Successfully processed batch {batch_num + 1}/{total_batches} ({len(batch_processed_repos)} repositories)")
    
    logger.info(f"Successfully processed all {len(all_processed_repos)} repositories in {total_batches} batches")
    return all_processed_repos


def _process_repository_batch(github_client: dict, repos: List[dict]) -> List[GraphQLRepoWrapper]:
    """
    Process a batch of repositories using ultra-optimized single GraphQL request.
    """
    logger.info(f"Executing mega GraphQL query for {len(repos)} repositories...")
    
    # Build the mega query with aliases for each repository
    query_parts = []
    variables = {}
    
    for i, repo in enumerate(repos):
        alias = f"repo{i}"
        query_parts.append(f"""
        {alias}: repository(owner: "{GITHUB_ORGANIZATION}", name: "{repo['name']}") {{
            name
            nameWithOwner
            url
            defaultBranchRef {{
                name
            }}
            # Get recent tags
            refs(first: 10, refPrefix: "refs/tags/", orderBy: {{field: TAG_COMMIT_DATE, direction: DESC}}) {{
                nodes {{
                    name
                    target {{
                        ... on Commit {{
                            oid
                            committedDate
                        }}
                    }}
                }}
            }}
            # Get workflow files content
            workflows: object(expression: "HEAD:.github/workflows") {{
                ... on Tree {{
                    entries {{
                        name
                        type
                        object {{
                            ... on Blob {{
                                text
                            }}
                        }}
                    }}
                }}
            }}
            # Get package.json content
            packageJson: object(expression: "HEAD:package.json") {{
                ... on Blob {{
                    text
                }}
            }}
        }}
        """)
    
    # Combine all parts
    query = f"""
    query {{
        {" ".join(query_parts)}
    }}
    """
    
    try:
        # Execute the query
        response = requests.post(
            github_client['url'],
            json={'query': query},
            headers=github_client['headers']
        )
        
        if response.status_code != 200:
            logger.error(f"GraphQL query failed: {response.status_code} - {response.text}")
            return []
        
        data = response.json()
        
        if 'errors' in data:
            logger.error(f"GraphQL errors: {data['errors']}")
            return []
        
        # Process results
        processed_repos = []
        for i, repo in enumerate(repos):
            alias = f"repo{i}"
            repo_data = data['data'].get(alias)
            
            if repo_data:
                processed_repo = _process_single_repository_data(repo_data, github_client)
                if processed_repo:
                    processed_repos.append(processed_repo)
                    logger.info(f"Processed {repo['name']} with {len(processed_repo._tags)} tags, {len(processed_repo._workflow_files)} workflow files")
        
        return processed_repos
        
    except Exception as e:
        logger.error(f"Error executing mega GraphQL query: {e}")
        return []


def get_repositories(github, organization=GITHUB_ORGANIZATION, patterns=REPO_PATTERNS):
    """Get list of repositories based on pattern using GraphQL."""
    logger.info("Finding repositories with GraphQL...")
    repos = []

    try:
        # GraphQL query to get repositories
        query = """
        query($org: String!, $first: Int!, $after: String) {
            organization(login: $org) {
                repositories(first: $first, after: $after) {
                    nodes {
                        name
                        nameWithOwner
                        url
                        defaultBranchRef {
                            name
                        }
                    }
                    pageInfo {
                        hasNextPage
                        endCursor
                    }
                }
            }
        }
        """
        
        variables = {
            "org": organization,
            "first": 100,
            "after": None
        }
        
        # Get all repositories (handle pagination)
        has_next_page = True
        while has_next_page:
            response = requests.post(
                github["url"], 
                json={"query": query, "variables": variables}, 
                headers=github["headers"]
            )
            
            if response.status_code != 200:
                logger.error(f"GraphQL API error: {response.status_code} - {response.text}")
                break
                
            data = response.json()
            if "errors" in data:
                logger.error(f"GraphQL errors: {data['errors']}")
                break
                
            org_data = data["data"]["organization"]
            if not org_data:
                logger.error(f"Organization {organization} not found")
                break
                
            # Filter repositories by pattern
            for repo in org_data["repositories"]["nodes"]:
                repo_name = repo["name"]
                
                # Check if repo name matches any pattern
                matches_pattern = False
                for pattern in patterns.split(','):
                    if pattern.strip().lower() in repo_name.lower():
                        matches_pattern = True
                        break
                
                if matches_pattern:
                    # Create repo object similar to PyGithub
                    repo_data = {
                        "name": repo["name"],
                        "full_name": repo["nameWithOwner"],
                        "url": repo["url"],
                        "default_branch": repo["defaultBranchRef"]["name"] if repo["defaultBranchRef"] else "main",
                        "_github_client": github  # Add GitHub client for other functions
                    }
                    repos.append(GraphQLRepoWrapper(repo_data, github))
            
            # Handle pagination
            page_info = org_data["repositories"]["pageInfo"]
            has_next_page = page_info["hasNextPage"]
            if has_next_page:
                variables["after"] = page_info["endCursor"]
        
        logger.info(f"Found {len(repos)} repositories matching pattern '{patterns}'")
        return repos
        
    except Exception as e:
        logger.error(f"Error getting repositories with GraphQL: {e}")
        logger.error(f"GraphQL repositories traceback:")
        logger.error(traceback.format_exc())
        return []


def fix_timezone(date):
    """Ensure date has timezone information."""
    if date.tzinfo is None:
        return date.replace(tzinfo=datetime.timezone.utc)
    return date


def get_repo_tags(repo, max_count=10):
    """Get the most recent tags for a repository using GraphQL."""
    # If we have pre-fetched tags, use them
    if hasattr(repo, '_tags') and repo._tags:
        logger.info(f"Using pre-fetched tags for {repo.name}")
        return repo._tags[:max_count]
    
    logger.info(f"Fetching {max_count} most recent tags for {repo.name} with GraphQL")

    all_tags = []
    
    try:
        # GraphQL query to get tags
        query = """
        query($owner: String!, $name: String!, $first: Int!) {
            repository(owner: $owner, name: $name) {
                refs(first: $first, refPrefix: "refs/tags/", orderBy: {field: TAG_COMMIT_DATE, direction: DESC}) {
                    nodes {
                        name
                        target {
                            ... on Commit {
                                oid
                                committedDate
                                message
                                url
                            }
                        }
                    }
                }
            }
        }
        """
        
        variables = {
            "owner": GITHUB_ORGANIZATION,
            "name": repo.name,
            "first": max_count
        }
        
        # Get GitHub client from repo object
        github_client = repo._github_client
        
        response = requests.post(
            github_client["url"], 
            json={"query": query, "variables": variables}, 
            headers=github_client["headers"]
        )
        
        if response.status_code != 200:
            logger.error(f"GraphQL API error: {response.status_code} - {response.text}")
            return all_tags
            
        data = response.json()
        if "errors" in data:
            logger.error(f"GraphQL errors: {data['errors']}")
            return all_tags
        
        repo_data = data["data"]["repository"]
        if not repo_data:
            logger.error(f"Repository {repo.name} not found")
            return all_tags
        
        # Process tags
        for ref in repo_data["refs"]["nodes"]:
            if ref["target"]:
                commit = ref["target"]
                commit_date = datetime.datetime.fromisoformat(commit["committedDate"].replace('Z', '+00:00'))
                
                tag_obj = {
                    'name': ref["name"],
                    'commit': commit["oid"],
                    'date': fix_timezone(commit_date),
                    'message': commit["message"],
                    'url': commit["url"]
                }
                
                all_tags.append(tag_obj)
        
        logger.info(f"Fetched {len(all_tags)} tags for {repo.name}")
        return all_tags
        
    except Exception as e:
        logger.error(f"Error getting tags for {repo.name}: {e}")
        return all_tags


def get_tags_in_period(repo, start_date, end_date):
    """Get tags created within a specified time period using GraphQL."""
    logger.info(
        f"Finding tags for {repo.name} between {start_date.strftime('%Y-%m-%d')} and {end_date.strftime('%Y-%m-%d')} with GraphQL")

    # Make sure dates have timezone information
    start_date = fix_timezone(start_date)
    end_date = fix_timezone(end_date)

    # Regex for matching semantic versions (e.g. 1.2.3)
    semver_pattern = re.compile(r'^v?\d+\.\d+\.\d+(-.*)?$')

    # Get recent tags
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
    """Get changes between two tags using GraphQL."""
    logger.info(f"Getting changes between {previous_tag['name']} and {current_tag['name']} in {repo.name}")

    # Initialize result
    result = {
        'changes': [],
        'ai_description': None
    }

    try:
        # Use the compare method from GraphQLRepoWrapper
        comparison = repo.compare(previous_tag['commit'], current_tag['commit'])
        
        if comparison is None:
            logger.error(f"Failed to get comparison for {repo.name}")
            return result
        
        # Process commits from comparison
        commits = list(comparison)
        
        for commit in commits:
            # Check if commit is a pull request merge
            pr_number = None
            pr_title = None

            # Look for PR reference in commit message
            merge_match = re.search(r'Merge pull request #(\d+)', commit["message"])
            if merge_match:
                pr_number = merge_match.group(1)

                # Extract the PR title from the commit message (usually after the first line)
                message_lines = commit["message"].strip().split('\n')
                if len(message_lines) > 1:
                    pr_title = message_lines[1].strip()

            # Create change entry
            change = {
                'commit_sha': commit["sha"],
                'commit_url': f"https://github.com/{GITHUB_ORGANIZATION}/{repo.name}/commit/{commit['sha']}",
                'commit_message': commit["message"],
                'author': commit["author"]["name"] if commit["author"] else "Unknown",
                'date': fix_timezone(datetime.datetime.fromisoformat(commit["author"]["date"].replace('Z', '+00:00'))) if commit["author"] and commit["author"]["date"] else None
            }

            # Add PR info if available
            if pr_number:
                change['pr_number'] = pr_number
                change['pr_url'] = f"https://github.com/{repo.full_name}/pull/{pr_number}"
                change['title'] = pr_title if pr_title else f"PR #{pr_number}"
            else:
                change['title'] = commit["message"].split('\n')[0]

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


def get_workflow_files_content(repo, github_client):
    """Get content of all workflow files in .github directory using GraphQL."""
    # If we have pre-fetched workflow files, use them
    if hasattr(repo, '_workflow_files') and repo._workflow_files:
        logger.info(f"Using pre-fetched workflow files for {repo.name}")
        return repo._workflow_files
    
    logger.info(f"Getting workflow files content for {repo.name} with GraphQL")
    
    workflow_files = []
    
    try:
        # First, get the tree structure of .github directory
        tree_query = """
        query($owner: String!, $name: String!, $path: String!) {
            repository(owner: $owner, name: $name) {
                object(expression: $path) {
                    ... on Tree {
                        entries {
                            name
                            type
                            object {
                                ... on Tree {
                                    entries {
                                        name
                                        type
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        """
        
        variables = {
            "owner": GITHUB_ORGANIZATION,
            "name": repo.name,
            "path": f"{repo.default_branch}:.github"
        }
        
        response = requests.post(
            github_client["url"], 
            json={"query": tree_query, "variables": variables}, 
            headers=github_client["headers"]
        )
        
        if response.status_code != 200:
            logger.warning(f"Could not access .github directory for {repo.name}: {response.status_code}")
            return workflow_files
            
        data = response.json()
        if "errors" in data:
            logger.warning(f"GraphQL errors for {repo.name}: {data['errors']}")
            return workflow_files
        
        repo_data = data["data"]["repository"]
        if not repo_data or not repo_data["object"]:
            logger.warning(f"No .github directory found for {repo.name}")
            return workflow_files
        
        # Collect all .yml and .yaml files
        yml_files = []
        
        def collect_yml_files(entries, current_path=""):
            for entry in entries:
                if entry["type"] == "tree":
                    # Recursively get subdirectory contents
                    sub_path = f"{repo.default_branch}:.github/{current_path}{entry['name']}"
                    sub_variables = {
                        "owner": GITHUB_ORGANIZATION,
                        "name": repo.name,
                        "path": sub_path
                    }
                    
                    sub_response = requests.post(
                        github_client["url"], 
                        json={"query": tree_query, "variables": sub_variables}, 
                        headers=github_client["headers"]
                    )
                    
                    if sub_response.status_code == 200:
                        sub_data = sub_response.json()
                        if "data" in sub_data and sub_data["data"]["repository"]["object"]:
                            collect_yml_files(
                                sub_data["data"]["repository"]["object"]["entries"],
                                f"{current_path}{entry['name']}/"
                            )
                elif entry["type"] == "blob" and entry["name"].endswith(('.yml', '.yaml')):
                    yml_files.append(f".github/{current_path}{entry['name']}")
        
        collect_yml_files(repo_data["object"]["entries"])
        
        # Get content of each .yml file
        content_query = """
        query($owner: String!, $name: String!, $path: String!) {
            repository(owner: $owner, name: $name) {
                object(expression: $path) {
                    ... on Blob {
                        text
                    }
                }
            }
        }
        """
        
        for file_path in yml_files:
            try:
                file_variables = {
                    "owner": GITHUB_ORGANIZATION,
                    "name": repo.name,
                    "path": f"{repo.default_branch}:{file_path}"
                }
                
                file_response = requests.post(
                    github_client["url"], 
                    json={"query": content_query, "variables": file_variables}, 
                    headers=github_client["headers"]
                )
                
                if file_response.status_code == 200:
                    file_data = file_response.json()
                    if "data" in file_data and file_data["data"]["repository"]["object"]:
                        workflow_files.append({
                            "path": file_path,
                            "content": file_data["data"]["repository"]["object"]["text"]
                        })
                        
            except Exception as e:
                logger.warning(f"Error getting content of {file_path}: {e}")
        
        logger.info(f"Found {len(workflow_files)} workflow files for {repo.name}")
        return workflow_files
        
    except Exception as e:
        logger.error(f"Error getting workflow files for {repo.name}: {e}")
        return workflow_files


def get_package_json_content(repo, github_client):
    """Get content of package.json file using GraphQL."""
    # If we have pre-fetched package.json, use it
    if hasattr(repo, '_package_json') and repo._package_json:
        logger.info(f"Using pre-fetched package.json for {repo.name}")
        return repo._package_json
    
    try:
        query = """
        query($owner: String!, $name: String!, $path: String!) {
            repository(owner: $owner, name: $name) {
                object(expression: $path) {
                    ... on Blob {
                        text
                    }
                }
            }
        }
        """
        
        variables = {
            "owner": GITHUB_ORGANIZATION,
            "name": repo.name,
            "path": f"{repo.default_branch}:package.json"
        }
        
        response = requests.post(
            github_client["url"], 
            json={"query": query, "variables": variables}, 
            headers=github_client["headers"]
        )
        
        if response.status_code == 200:
            data = response.json()
            if "data" in data and data["data"]["repository"]["object"]:
                return data["data"]["repository"]["object"]["text"]
        
        return None
        
    except Exception as e:
        logger.warning(f"Error getting package.json for {repo.name}: {e}")
        return None


def extract_component_names_from_workflow_files(workflow_files):
    """Extract component names from workflow files using the same logic as component_utils.py."""
    component_names = set()
    vendors = set()
    
    for file_data in workflow_files:
        try:
            content = file_data["content"]
            lines = content.split('\n')
            
            for line in lines:
                if not line.strip():
                    continue
                    
                # Find component identifiers - ensure values are on the same line
                # Match patterns like: KEY: value, KEY: "value", KEY: 'value'
                app_match = re.search(r'(?i)KBC_DEVELOPERPORTAL_APP\s*:\s*[\'"]?([a-zA-Z0-9._-]+)[\'"]?', line)
                id_match = re.search(r'(?i)KBC_DEVELOPERPORTAL_ID\s*:\s*[\'"]?([a-zA-Z0-9._-]+)[\'"]?', line)
                app_name_match = re.search(r'(?i)APP_NAME\s*:\s*[\'"]?([a-zA-Z0-9._-]+)[\'"]?', line)
                vendor_match = re.search(r'(?i)KBC_DEVELOPERPORTAL_VENDOR\s*:\s*[\'"]?([a-zA-Z0-9._-]+)[\'"]?', line)
                
                # Add component matches
                for match in [app_match, id_match, app_name_match]:
                    if match and match.group(1) and not match.group(1).startswith('${{'):
                        component_names.add(match.group(1))
                
                # Add vendor match
                if vendor_match and vendor_match.group(1) and not vendor_match.group(1).startswith('${{'):
                    vendors.add(vendor_match.group(1))
                    
        except Exception as e:
            logger.warning(f"Error processing workflow file {file_data['path']}: {e}")
    
    return component_names, vendors


def extract_component_id_from_package_json(package_json_content):
    """Extract component ID from package.json content."""
    if not package_json_content:
        return None
        
    try:
        package_data = json.loads(package_json_content)
        
        # Look for componentId in various locations
        component_id = None
        
        # Check for keboola.componentId
        if "keboola" in package_data and "componentId" in package_data["keboola"]:
            component_id = package_data["keboola"]["componentId"]
        
        # Check for componentId directly in package.json
        elif "componentId" in package_data:
            component_id = package_data["componentId"]
            
        return component_id
        
    except Exception as e:
        logger.debug(f"Could not extract component ID from package.json: {e}")
        return None


def get_component_name(repo, github_client):
    """Extract component names from workflow files using GraphQL.
    Returns a list of component names found in .github/*.yml files.
    Uses the same logic as component_utils.py but with GraphQL API.
    """
    component_names = set()
    vendors = set()
    github_dir_accessible = True

    try:
        # Get workflow files content
        workflow_files = get_workflow_files_content(repo, github_client)
        
        if not workflow_files:
            logger.warning(f"No workflow files found for repo {repo.name}, could be a permission issue")
            github_dir_accessible = False
        
        # Extract component names from workflow files
        if workflow_files:
            component_names, vendors = extract_component_names_from_workflow_files(workflow_files)
    
    except Exception as e:
        logger.warning(f"Error accessing workflow files in {repo.name}: {e}")
        github_dir_accessible = False
    
    # If .github was not accessible or no component names found, try alternative methods
    if not github_dir_accessible or not component_names:
        # Try to get component ID from package.json
        try:
            package_json_content = get_package_json_content(repo, github_client)
            if package_json_content:
                component_id = extract_component_id_from_package_json(package_json_content)
                if component_id:
                    component_names.add(component_id)
                    logger.info(f"Found component ID {component_id} from package.json in {repo.name}")
        except Exception as e:
            logger.warning(f"Error extracting from package.json in {repo.name}: {e}")
    
    # If still no component names found, use repo name with standard prefixes
    if not component_names:
        logger.info(f"No component ID found, using repo name for {repo.name}")
        # If repo name starts with "component-" prefix, extract the component name
        repo_name = repo.name
        if repo_name.startswith("component-"):
            extracted_name = repo_name[10:]  # Remove "component-" prefix
            # Add keboola. prefix as default vendor if no vendor found
            if not vendors:
                component_names.add(f"keboola.{extracted_name}")
            else:
                for vendor in vendors:
                    component_names.add(f"{vendor}.{extracted_name}")
        else:
            component_names.add(repo_name)
    
    # Process vendor prefixes for components without dots
    final_component_names = set()
    for component_name in component_names:
        if '.' not in component_name:
            # For components without dots, try to prefix with vendor
            if vendors:
                for vendor in vendors:
                    vendor_prefixed = f"{vendor}.{component_name}"
                    final_component_names.add(vendor_prefixed)
                
                # Also keep the original if multiple vendors
                if len(vendors) > 1:
                    final_component_names.add(component_name)
            else:
                # If no vendors found, add keboola as default vendor
                final_component_names.add(f"keboola.{component_name}")
        else:
            # Components with dots are kept as-is
            final_component_names.add(component_name)
    
    return list(final_component_names) 


def _process_single_repository_data(repo_data: dict, github_client: dict) -> GraphQLRepoWrapper:
    """
    Process single repository data from GraphQL response.
    """
    try:
        # Process tags
        tags = []
        if repo_data.get("refs"):
            for ref in repo_data["refs"]["nodes"]:
                if ref.get("target"):
                    commit = ref["target"]
                    commit_date = datetime.datetime.fromisoformat(commit["committedDate"].replace('Z', '+00:00'))
                    
                    tag_obj = {
                        'name': ref["name"],
                        'commit': commit["oid"],
                        'date': fix_timezone(commit_date)
                    }
                    tags.append(tag_obj)
        
        # Process workflow files content
        workflow_files = []
        if repo_data.get("workflows") and repo_data["workflows"].get("entries"):
            for entry in repo_data["workflows"]["entries"]:
                if entry["type"] == "blob" and entry["name"].endswith(('.yml', '.yaml')):
                    if entry.get("object") and entry["object"].get("text"):
                        workflow_files.append({
                            "path": f".github/workflows/{entry['name']}",
                            "content": entry["object"]["text"]
                        })
        
        # Process package.json
        package_json = None
        if repo_data.get("packageJson") and repo_data["packageJson"].get("text"):
            package_json = repo_data["packageJson"]["text"]
        
        # Create complete repo object
        complete_repo_data = {
            "name": repo_data["name"],
            "full_name": repo_data["nameWithOwner"],
            "url": repo_data["url"],
            "default_branch": repo_data["defaultBranchRef"]["name"] if repo_data.get("defaultBranchRef") else "main",
            "_github_client": github_client,
            "_tags": tags,
            "_workflow_files": workflow_files,
            "_package_json": package_json
        }
        
        return GraphQLRepoWrapper(complete_repo_data, github_client)
        
    except Exception as e:
        logger.error(f"Error processing repository data for {repo_data.get('name', 'unknown')}: {e}")
        return None 