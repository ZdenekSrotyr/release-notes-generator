#!/usr/bin/env python3
import os
import sys
import yaml
import json
import argparse
import datetime
import requests
import logging
import re
import glob
from pathlib import Path
from github import Github
from jinja2 import Environment, FileSystemLoader

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('release-notes-generator')

class ReleaseNotesGenerator:
    def __init__(self, args):
        """Initialize the generator with arguments."""
        logger.info(f"Initializing generator")
        
        # Store command line arguments
        self.args = args
        
        # Store single repo override if provided
        self.single_repo = args.repo
        if self.single_repo:
            logger.info(f"Single repository mode: {self.single_repo}")
        
        # GitHub configuration
        self.github_token = os.environ.get('GITHUB_TOKEN')
        if not self.github_token:
            logger.error("GitHub token is missing")
            raise ValueError("GitHub token is required. Set GITHUB_TOKEN env variable.")
        else:
            logger.info("GitHub token found")
        
        self.github = Github(self.github_token)
        self.organization = args.organization
        
        # Time period configuration
        if args.since_last_run:
            logger.info("Using since-last-run mode, will detect time period from previous run")
            self.time_period = self._detect_time_period_from_last_run()
        else:
            self.time_period = args.time_period
        
        logger.info(f"Time period set to: {self.time_period}")
        
        # Template and output configuration
        self.template_dir = args.template_dir
        self.output_file = args.output_file
        logger.info(f"Output will be written to: {self.output_file}")
        
        # Directory for individual component release notes
        self.release_notes_dir = args.release_notes_dir
        self.only_new_releases = args.only_new_releases
        logger.info(f"Individual release notes will be saved to: {self.release_notes_dir}")
        if self.only_new_releases:
            logger.info("Only processing new releases that haven't been saved before")
        
        # Ensure release notes directory exists
        os.makedirs(self.release_notes_dir, exist_ok=True)
        
        # AI configuration
        self.use_ai = args.use_ai
        self.ai_provider = 'openai'  # Currently only supporting OpenAI
        self.ai_api_key = os.environ.get('AI_API_KEY')
        
        if self.use_ai:
            if self.ai_api_key:
                logger.info(f"AI generation enabled with provider: {self.ai_provider}")
            else:
                logger.warning("AI generation enabled but no API key provided")
                self.use_ai = False
        
        # Slack configuration
        self.slack_enabled = args.slack_enabled
        self.slack_webhook_url = os.environ.get('SLACK_WEBHOOK_URL')
        
        if self.slack_enabled:
            if self.slack_webhook_url:
                logger.info("Slack integration enabled")
            else:
                logger.warning("Slack integration enabled but no webhook URL provided")
                self.slack_enabled = False
    
    def _detect_time_period_from_last_run(self):
        """Detect time period by parsing the last generated release notes file."""
        try:
            if not os.path.exists(self.args.output_file):
                logger.warning(f"Previous output file {self.args.output_file} not found. Using default time period.")
                return self.args.time_period
            
            logger.info(f"Analyzing previous release notes file: {self.args.output_file}")
            
            # Read the file
            with open(self.args.output_file, 'r') as f:
                content = f.read()
            
            # Look for the date of the most recent entry
            date_pattern = r'### (\d{4}-\d{2}-\d{2}) -'
            dates = re.findall(date_pattern, content)
            
            if not dates:
                logger.warning("No dates found in previous release notes. Using default time period.")
                return self.args.time_period
            
            # Find the most recent date
            most_recent_date = max(dates)
            logger.info(f"Most recent date found in release notes: {most_recent_date}")
            
            # Create a custom time period from that date to now
            today = datetime.datetime.now().strftime('%Y-%m-%d')
            time_period = f"{most_recent_date}-to-{today}"
            logger.info(f"Setting time period to: {time_period}")
            
            return time_period
            
        except Exception as e:
            logger.error(f"Error detecting time period from last run: {e}")
            return self.args.time_period
        
    def get_date_range(self):
        """Convert time period to actual dates."""
        logger.info(f"Calculating date range for time period: {self.time_period}")
        today = datetime.datetime.now(datetime.timezone.utc)  # Use UTC timezone-aware datetime
        
        if self.time_period == 'last-week':
            start_date = today - datetime.timedelta(days=7)
            logger.info(f"Date range: last 7 days ({start_date.strftime('%Y-%m-%d')} to {today.strftime('%Y-%m-%d')})")
        elif self.time_period == 'last-month':
            start_date = today - datetime.timedelta(days=30)
            logger.info(f"Date range: last 30 days ({start_date.strftime('%Y-%m-%d')} to {today.strftime('%Y-%m-%d')})")
        elif self.time_period == 'last-quarter':
            start_date = today - datetime.timedelta(days=90)
            logger.info(f"Date range: last 90 days ({start_date.strftime('%Y-%m-%d')} to {today.strftime('%Y-%m-%d')})")
        elif '-to-' in self.time_period:
            # Handle custom date range like "2023-01-01-to-2023-02-01"
            start_str, end_str = self.time_period.split('-to-')
            start_date = datetime.datetime.strptime(start_str, '%Y-%m-%d')
            end_date = datetime.datetime.strptime(end_str, '%Y-%m-%d')
            # Make them timezone-aware with UTC
            start_date = start_date.replace(tzinfo=datetime.timezone.utc)
            end_date = end_date.replace(tzinfo=datetime.timezone.utc)
            logger.info(f"Date range: custom period ({start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')})")
            return start_date, end_date
        else:
            # Default to last month
            start_date = today - datetime.timedelta(days=30)
            logger.info(f"Using default date range: last 30 days ({start_date.strftime('%Y-%m-%d')} to {today.strftime('%Y-%m-%d')})")
            
        return start_date, today
        
    def get_repos(self):
        """Get list of repositories based on configuration."""
        logger.info("Finding repositories...")
        repos = []
        
        # If single repo is specified, use that instead of configured repos
        if self.single_repo:
            logger.info(f"Using specified repository: {self.single_repo}")
            try:
                # Check if it's a full name (org/repo) or just repo name
                if '/' in self.single_repo:
                    full_name = self.single_repo
                else:
                    if not self.organization:
                        logger.error(f"No organization specified and repository '{self.single_repo}' does not include organization")
                        return []
                    full_name = f"{self.organization}/{self.single_repo}"
                
                logger.info(f"Fetching repository: {full_name}")
                repos.append(self.github.get_repo(full_name))
                logger.info(f"Repository {full_name} found and added")
                return repos
            except Exception as e:
                logger.error(f"Failed to find repository {self.single_repo}: {e}")
                return []
        
        # Get repos by pattern
        if self.args.repo_patterns:
            for pattern in self.args.repo_patterns.split(','):
                logger.info(f"Searching for repos with pattern: {pattern}")
                query = f"org:{self.organization} {pattern} in:name"
                logger.debug(f"GitHub API query: {query}")
                
                search_results = self.github.search_repositories(query=query)
                count = 0
                for repo in search_results:
                    repos.append(repo)
                    count += 1
                
                logger.info(f"Found {count} repositories matching pattern '{pattern}'")
        
        # Get explicitly listed repos
        if self.args.repos:
            repo_list = self.args.repos.split(',')
            logger.info(f"Adding {len(repo_list)} explicitly listed repositories")
            for repo_name in repo_list:
                full_name = f"{self.organization}/{repo_name.strip()}"
                logger.debug(f"Adding repository: {full_name}")
                try:
                    repos.append(self.github.get_repo(full_name))
                except Exception as e:
                    logger.error(f"Failed to find repository {full_name}: {e}")
        
        logger.info(f"Total repositories to process: {len(repos)}")
        return repos
    
    def get_component_name(self, repo):
        """Extract component name from workflow file."""
        logger.debug(f"Extracting component name for {repo.name}")
        try:
            workflow_path = ".github/workflows/push.yml"
            logger.debug(f"Looking for workflow file at {workflow_path}")
            workflow_content = repo.get_contents(workflow_path).decoded_content.decode('utf-8')
            workflow_yaml = yaml.safe_load(workflow_content)
            
            # Look for KBC_DEVELOPERPORTAL_APP in env section
            if 'env' in workflow_yaml:
                component_name = workflow_yaml['env'].get('KBC_DEVELOPERPORTAL_APP', repo.name)
                if component_name != repo.name:
                    logger.debug(f"Found component name in env section: {component_name}")
                    return component_name
            
            # Try to find it in jobs
            for job_name, job in workflow_yaml.get('jobs', {}).items():
                if 'env' in job and 'KBC_DEVELOPERPORTAL_APP' in job['env']:
                    component_name = job['env']['KBC_DEVELOPERPORTAL_APP']
                    logger.debug(f"Found component name in job {job_name}: {component_name}")
                    return component_name
            
            # Default to repo name if not found
            logger.debug(f"No component name found, using repo name: {repo.name}")
            return repo.name
        except Exception as e:
            logger.warning(f"Could not extract component name for {repo.name}: {e}")
            return repo.name
        
    def get_tags_in_period(self, repo, start_date, end_date):
        """Get tags created in the specified period."""
        logger.info(f"Retrieving tags for {repo.name} between {start_date.strftime('%Y-%m-%d')} and {end_date.strftime('%Y-%m-%d')}")
        tags = []
        
        try:
            all_tags = list(repo.get_tags())
            logger.debug(f"Total tags found in {repo.name}: {len(all_tags)}")
            
            for tag in all_tags:
                # Get the commit date
                commit = tag.commit
                commit_date = commit.commit.author.date
                
                # Make sure we're comparing timezone-aware dates consistently
                if commit_date.tzinfo is None:
                    commit_date = commit_date.replace(tzinfo=datetime.timezone.utc)
                
                if start_date <= commit_date <= end_date:
                    logger.debug(f"Tag {tag.name} from {commit_date.strftime('%Y-%m-%d')} is within date range")
                    tags.append({
                        'name': tag.name,
                        'date': commit_date,
                        'commit': commit.sha,
                        'message': commit.commit.message,
                        'url': tag.commit.html_url
                    })
            
            logger.info(f"Found {len(tags)} tags in {repo.name} within date range")
            return sorted(tags, key=lambda x: x['date'])
        except Exception as e:
            logger.error(f"Error retrieving tags for {repo.name}: {e}")
            return []
        
    def get_changes_between_tags(self, repo, older_tag, newer_tag):
        """Get changes between two tags."""
        logger.info(f"Comparing changes between {older_tag['name']} and {newer_tag['name']} in {repo.name}")
        
        try:
            logger.debug(f"Using comparison: {older_tag['commit']} ... {newer_tag['commit']}")
            comparison = repo.compare(older_tag['commit'], newer_tag['commit'])
            
            # Convert PaginatedList to a normal list before checking length
            commits_list = list(comparison.commits)
            logger.debug(f"Found {len(commits_list)} commits between tags")
            
            # Additional logging to help diagnose the issue
            if len(commits_list) == 0:
                logger.warning(f"No commits found between {older_tag['name']} and {newer_tag['name']}. This may indicate an issue with tag ordering or GitHub API access.")
                # Try direct approach to get commits
                try:
                    # Get all commits and filter between dates
                    older_commit = repo.get_commit(older_tag['commit'])
                    newer_commit = repo.get_commit(newer_tag['commit']) 
                    older_date = older_commit.commit.author.date
                    newer_date = newer_commit.commit.author.date
                    
                    logger.debug(f"Trying to find commits between dates: {older_date} and {newer_date}")
                    
                    # Ensure dates are in correct order
                    if older_date > newer_date:
                        logger.warning(f"Tag dates are in wrong order. Swapping comparison direction.")
                        older_date, newer_date = newer_date, older_date
                    
                    # Get commits in date range
                    commits_in_range = list(repo.get_commits(since=older_date, until=newer_date))
                    logger.info(f"Found {len(commits_in_range)} commits by date range between {older_date} and {newer_date}")
                    
                    # Use these commits instead if found
                    if len(commits_in_range) > 0:
                        commits_list = commits_in_range
                except Exception as e:
                    logger.error(f"Failed to get commits by date: {e}")
                    
            changes = []
            
            # Get PR information from commits
            logger.debug("Extracting PR information from commits")
            for commit in commits_list:  # Use the converted list here
                # Extract PR number from commit message if available
                pr_number = None
                message = commit.commit.message
                if '(#' in message:
                    pr_part = message.split('(#')[1]
                    if ')' in pr_part:
                        pr_number = pr_part.split(')')[0]
                
                if pr_number:
                    try:
                        logger.debug(f"Found PR #{pr_number}, fetching details")
                        pr = repo.get_pull(int(pr_number))
                        changes.append({
                            'title': pr.title,
                            'number': pr.number,
                            'url': pr.html_url,
                            'body': pr.body,
                            'merged_at': pr.merged_at
                        })
                    except Exception as e:
                        logger.warning(f"Failed to fetch PR #{pr_number}: {e}")
                        # If PR can't be found, use commit info
                        changes.append({
                            'title': commit.commit.message.split('\n')[0],
                            'commit': commit.sha,
                            'url': commit.html_url
                        })
                else:
                    logger.debug(f"No PR reference found in commit {commit.sha[:7]}")
                    changes.append({
                        'title': commit.commit.message.split('\n')[0],
                        'commit': commit.sha,
                        'url': commit.html_url
                    })
            
            logger.info(f"Comparison complete: {len(changes)} changes")
            
            # Generate AI description if enabled
            ai_description = None
            if self.use_ai and self.ai_api_key:
                logger.info("Generating AI description for changes")
                ai_description = self.generate_ai_description(
                    repo.name, 
                    older_tag['name'], 
                    newer_tag['name'],
                    changes
                )
                    
            return {
                'changes': changes,
                'ai_description': ai_description
            }
        except Exception as e:
            logger.error(f"Error comparing tags in {repo.name}: {e}")
            return {
                'changes': [],
                'ai_description': None
            }
    
    def generate_ai_description(self, repo_name, old_tag, new_tag, changes):
        """Generate an AI-powered description of changes between tags."""
        logger.info(f"Generating AI description for {repo_name} from {old_tag} to {new_tag}")
        
        if self.ai_provider == 'openai':
            return self.generate_openai_description(repo_name, old_tag, new_tag, changes)
        else:
            logger.warning(f"Unsupported AI provider {self.ai_provider}")
            return None
    
    def generate_openai_description(self, repo_name, old_tag, new_tag, changes):
        """Generate a description using OpenAI."""
        try:
            if not self.ai_api_key:
                logger.warning("OpenAI API key not provided, skipping AI description")
                return None
                
            import openai
            client = openai.OpenAI(api_key=self.ai_api_key)
            
            # Prepare context for the AI
            commit_messages = [change.get('title', '') for change in changes]
            
            logger.debug(f"Preparing OpenAI prompt with {len(commit_messages)} commit messages")
                        
            prompt = f"""
            Analyze these changes from {repo_name} between tags {old_tag} and {new_tag} and provide a concise summary:
            
            Commit messages:
            {json.dumps(commit_messages, indent=2)}
            
            Please provide:
            1. A short summary of the main changes (1-2 sentences)
            2. The key improvements or features added
            3. Any breaking changes or important notes
            """
            
            try:
                # Using the new OpenAI API (1.0.0+)
                response = client.completions.create(
                    model="gpt-3.5-turbo-instruct",
                    prompt=prompt,
                    max_tokens=300,
                    temperature=0.5
                )
                
                ai_description = response.choices[0].text.strip()
                logger.info(f"AI description generated successfully ({len(ai_description)} chars)")
                return ai_description
            except Exception as api_error:
                logger.error(f"Error calling OpenAI API: {api_error}")
                return f"Error generating AI description: {str(api_error)[:100]}..."
                
        except Exception as e:
            logger.error(f"Error generating AI description: {e}")
            return None
    
    def generate_timeline(self):
        """Generate a timeline of all changes across repositories."""
        logger.info("Generating timeline of changes")
        start_date, end_date = self.get_date_range()
        repos = self.get_repos()
        
        # Timeline will be a list of events
        timeline = []
        new_releases = []  # Track new releases for Slack notification
        
        for i, repo in enumerate(repos):
            logger.info(f"Processing repository {i+1}/{len(repos)}: {repo.name}")
            
            component_name = self.get_component_name(repo)
            logger.info(f"Component name resolved to: {component_name}")
            
            # Get all tags and sort them by date first to ensure proper chronological order
            try:
                logger.debug("Getting all tags from repository for proper chronological sorting")
                all_repo_tags = []
                all_tags_api = list(repo.get_tags())
                logger.info(f"Total tags retrieved from API: {len(all_tags_api)}")
                
                for tag in all_tags_api:
                    try:
                        commit = tag.commit
                        commit_date = commit.commit.author.date
                        
                        # Make sure we're comparing timezone-aware dates consistently
                        if commit_date.tzinfo is None:
                            commit_date = commit_date.replace(tzinfo=datetime.timezone.utc)
                        
                        all_repo_tags.append({
                            'name': tag.name,
                            'date': commit_date,
                            'commit': commit.sha,
                            'message': commit.commit.message,
                            'url': tag.commit.html_url
                        })
                        logger.debug(f"Added tag {tag.name} from {commit_date.strftime('%Y-%m-%d %H:%M:%S')}")
                    except Exception as e:
                        logger.warning(f"Error processing tag {tag.name}: {e}")
                
                # Sort all tags chronologically (oldest first)
                all_repo_tags = sorted(all_repo_tags, key=lambda x: x['date'])
                logger.info(f"Repository has {len(all_repo_tags)} tags in total, sorted chronologically")
                
                # Log all tags in chronological order for debugging
                logger.debug("All tags in chronological order:")
                for idx, tag in enumerate(all_repo_tags):
                    logger.debug(f"{idx+1}. {tag['name']} from {tag['date'].strftime('%Y-%m-%d %H:%M:%S')}")
                
                # Filter tags in specified period
                tags = []
                for tag in all_repo_tags:
                    # Check if we should only process new releases
                    date_str = tag['date'].strftime('%Y-%m-%d')
                    component_name_normalized = component_name.replace('.', '-').replace(' ', '-').lower()
                    file_name = f"{date_str}_{component_name_normalized}_{tag['name']}.md"
                    file_path = os.path.join(self.release_notes_dir, file_name)
                    
                    # Skip if we're only processing new releases and this one exists
                    if self.only_new_releases and os.path.exists(file_path):
                        logger.debug(f"Skipping existing release: {component_name} {tag['name']} from {date_str}")
                        continue
                    
                    if start_date <= tag['date'] <= end_date:
                        tags.append(tag)
                        logger.debug(f"Tag {tag['name']} from {tag['date'].strftime('%Y-%m-%d %H:%M:%S')} is within date range")
                
                logger.info(f"Found {len(tags)} tags in {repo.name} within date range")
            except Exception as e:
                logger.error(f"Failed to process tags for {repo.name}: {e}")
                continue
            
            # Skip if no tags in period
            if not tags:
                logger.info(f"No tags found in date range for {repo.name}, skipping")
                continue
                
            # Process each tag
            logger.info(f"Processing {len(tags)} tags for {repo.name}")
            for i, tag in enumerate(tags):
                logger.debug(f"Processing tag {i+1}/{len(tags)}: {tag['name']} from {tag['date'].strftime('%Y-%m-%d %H:%M:%S')}")
                
                # Find the previous tag in the chronological order
                previous_tag = None
                
                if i > 0:
                    # Use the previous tag in our period
                    previous_tag = tags[i-1]
                    logger.debug(f"Using previous tag in period: {previous_tag['name']} from {previous_tag['date'].strftime('%Y-%m-%d %H:%M:%S')}")
                else:
                    # Find the tag that immediately precedes the first tag in our period
                    tag_index = all_repo_tags.index(tag)
                    if tag_index > 0:
                        previous_tag = all_repo_tags[tag_index - 1]
                        logger.debug(f"Using tag outside period as previous: {previous_tag['name']} from {previous_tag['date'].strftime('%Y-%m-%d %H:%M:%S')}")
                    else:
                        # If this is the first tag ever, use the initial commit
                        try:
                            logger.debug(f"No previous tag found, using initial commit")
                            initial_commit = list(repo.get_commits().reversed())[-1]
                            previous_tag = {
                                'name': 'initial',
                                'commit': initial_commit.sha,
                                'date': initial_commit.commit.author.date,
                                'message': initial_commit.commit.message,
                                'url': initial_commit.html_url
                            }
                            logger.debug(f"Using initial commit: {previous_tag['commit']} from {previous_tag['date'].strftime('%Y-%m-%d %H:%M:%S')}")
                        except Exception as e:
                            logger.warning(f"Failed to find initial commit: {e}")
                            # Use tag's own commit but from 1 day before as a fallback
                            previous_date = tag['date'] - datetime.timedelta(days=1)
                            previous_tag = {
                                'name': 'initial',
                                'commit': tag['commit'],
                                'date': previous_date,
                                'message': 'Initial state',
                                'url': tag['url']
                            }
                            logger.debug(f"Using fallback initial state from {previous_date.strftime('%Y-%m-%d %H:%M:%S')}")
                
                logger.debug(f"Previous tag for {tag['name']} is {previous_tag['name']}")
                
                # Ensure older_tag is chronologically before newer_tag
                if previous_tag['date'] > tag['date']:
                    logger.warning(f"Tag order issue: {previous_tag['name']} ({previous_tag['date'].strftime('%Y-%m-%d')}) is newer than {tag['name']} ({tag['date'].strftime('%Y-%m-%d')}). Swapping order for comparison.")
                    change_data = self.get_changes_between_tags(repo, tag, previous_tag)
                else:
                    change_data = self.get_changes_between_tags(repo, previous_tag, tag)
                
                # Check if we actually got changes
                if not change_data['changes']:
                    logger.warning(f"No changes found between {previous_tag['name']} and {tag['name']}. Trying additional methods.")
                    # Try a direct approach with GitHub API
                    try:
                        # Get direct diff URL for manual inspection
                        diff_url = f"https://github.com/{repo.full_name}/compare/{previous_tag['name']}...{tag['name']}"
                        logger.info(f"You can inspect diff manually at: {diff_url}")
                        
                        # Try to get raw diff
                        headers = {'Authorization': f'token {self.github_token}'}
                        diff_api_url = f"https://api.github.com/repos/{repo.full_name}/compare/{previous_tag['name']}...{tag['name']}"
                        logger.debug(f"Fetching diff from API: {diff_api_url}")
                        diff_response = requests.get(diff_api_url, headers=headers)
                        
                        if diff_response.status_code == 200:
                            diff_data = diff_response.json()
                            if 'commits' in diff_data and diff_data['commits']:
                                logger.info(f"Found {len(diff_data['commits'])} commits in API response")
                                # Create changes from commits
                                for commit in diff_data['commits']:
                                    change_data['changes'].append({
                                        'title': commit['commit']['message'].split('\n')[0],
                                        'commit': commit['sha'],
                                        'url': commit['html_url']
                                    })
                        else:
                            logger.warning(f"API request failed with status {diff_response.status_code}: {diff_response.text}")
                    except Exception as e:
                        logger.error(f"Failed to get direct diff: {e}")
                
                # Create entry for this release
                entry = {
                    'date': tag['date'],
                    'type': 'release',
                    'repo_name': repo.name,
                    'component_name': component_name,
                    'tag_name': tag['name'],
                    'tag_url': f"https://github.com/{repo.full_name}/releases/tag/{tag['name']}",
                    'changes': change_data['changes'],
                    'ai_description': change_data['ai_description'],
                    'previous_tag': previous_tag['name']
                }
                
                # Save individual release note
                is_new = self.save_component_release_note(entry)
                if is_new:
                    new_releases.append(entry)
                
                # Add to timeline for main release notes
                timeline.append(entry)
                logger.debug(f"Added {tag['name']} to timeline with {len(change_data['changes'])} changes")
        
        # Sort timeline by date (newest first)
        logger.info(f"Sorting timeline entries (total: {len(timeline)})")
        timeline.sort(key=lambda x: x['date'], reverse=True)
        
        # Save the list of new releases for Slack notification
        self.new_releases = new_releases
        
        return timeline
    
    def save_component_release_note(self, entry):
        """Save a release note for a single component release."""
        # Format: YYYY-MM-DD_component-name.md
        date_str = entry['date'].strftime('%Y-%m-%d')
        component_name = entry['component_name'].replace('.', '-').replace(' ', '-').lower()
        file_name = f"{date_str}_{component_name}_{entry['tag_name']}.md"
        file_path = os.path.join(self.release_notes_dir, file_name)
        
        # Check if this release note already exists
        if os.path.exists(file_path):
            logger.info(f"Release note for {component_name} {entry['tag_name']} already exists, skipping")
            return False
        
        # Create the release note content
        template_loader = FileSystemLoader(self.template_dir)
        template_env = Environment(loader=template_loader)
        template = template_env.get_template('component-release.md.j2')
        
        # Render the template
        content = template.render(
            entry=entry,
            generated_at=datetime.datetime.now(datetime.timezone.utc)
        )
        
        # Write the file
        with open(file_path, 'w') as f:
            f.write(content)
        
        logger.info(f"Created release note: {file_path}")
        return True
    
    def generate_markdown(self):
        """Generate markdown content."""
        logger.info("Generating markdown content")
        
        try:
            timeline = self.generate_timeline()
            logger.info(f"Timeline generated with {len(timeline)} entries")
            
            logger.debug("Loading Jinja2 template")
            env = Environment(loader=FileSystemLoader(self.template_dir))
            template = env.get_template('release-notes.md.j2')
            
            logger.debug("Rendering template")
            content = template.render(
                timeline=timeline,
                generated_at=datetime.datetime.now(datetime.timezone.utc),  # Use UTC timezone-aware datetime
                time_period=self.time_period
            )
            
            logger.info(f"Writing content to {self.output_file}")
            with open(self.output_file, 'w') as f:
                f.write(content)
                
            logger.info(f"Release notes generated successfully in {self.output_file}")
            
            # Send to Slack if enabled
            if self.slack_enabled and self.slack_webhook_url:
                logger.info("Sending release notes to Slack")
                self.send_to_slack(content)
            
            return True
        except Exception as e:
            logger.error(f"Error generating markdown content: {e}")
            return False
    
    def send_to_slack(self, content=None):
        """Send release notes to Slack webhook."""
        logger.info("Preparing to send release notes to Slack")
        
        # If we're only sending new releases
        if self.only_new_releases and hasattr(self, 'new_releases'):
            if not self.new_releases:
                logger.info("No new releases to send to Slack")
                return
            
            logger.info(f"Sending {len(self.new_releases)} new releases to Slack")
            
            try:
                # Create a list of links to component releases
                components_updated = []
                summary_text = ""
                
                for entry in self.new_releases:
                    component = entry['component_name']
                    tag = entry['tag_name']
                    components_updated.append(f"*{component}* {tag}")
                    
                    # Add a summary for this component
                    summary_text += f"*{component}* {tag} - {entry['date'].strftime('%Y-%m-%d')}:\n"
                    
                    # Add the AI description if available
                    if entry['ai_description']:
                        # Limit to first 150 chars
                        desc = entry['ai_description'][:150]
                        if len(entry['ai_description']) > 150:
                            desc += "..."
                        summary_text += f"_{desc}_\n"
                    
                    # Add a few changes
                    if entry['changes']:
                        for i, change in enumerate(entry['changes'][:3]):
                            summary_text += f"• {change['title']}\n"
                        if len(entry['changes']) > 3:
                            summary_text += f"_...and {len(entry['changes']) - 3} more changes_\n"
                    
                    summary_text += f"<{entry['tag_url']}|View on GitHub>\n\n"
                
                # Format content for Slack
                logger.debug("Creating Slack message")
                title = f"*New Release Notes for {self.time_period}*\n\n"
                
                # Prepare the payload
                logger.debug("Preparing Slack payload")
                slack_payload = {
                    "text": title + summary_text,
                    "attachments": [
                        {
                            "title": f"New Releases: {', '.join(components_updated)}",
                            "text": "See the message above for details",
                            "color": "#36C5F0"
                        }
                    ]
                }
                
                # Post to Slack
                logger.info("Sending message to Slack webhook")
                response = requests.post(
                    self.slack_webhook_url,
                    json=slack_payload
                )
                
                # Check if message was posted successfully
                if response.status_code != 200:
                    logger.warning(f"Failed to send message to Slack: {response.text}")
                else:
                    logger.info("Release notes sent to Slack successfully!")
                    
            except Exception as e:
                logger.error(f"Error sending to Slack: {e}")
        else:
            # Original behavior - send the complete file
            try:
                # Format content for Slack
                # Create a simple summary for Slack
                logger.debug("Creating Slack message")
                summary = f"*Release Notes for {self.time_period}*\n\n"
                
                # Add a summary of components updated
                components_updated = set()
                for entry in self.generate_timeline():
                    components_updated.add(entry['component_name'])
                
                summary += f"*Components updated:* {', '.join(sorted(components_updated))}\n\n"
                summary += f"*Details:* See the attached file for complete release notes."
                
                # Prepare the payload
                logger.debug("Preparing Slack payload")
                slack_payload = {
                    "text": summary,
                    "attachments": [
                        {
                            "title": f"Release Notes - {self.time_period}",
                            "text": "See the attached file for details.",
                            "color": "#36C5F0"
                        }
                    ]
                }
                
                # Post to Slack
                logger.info("Sending message to Slack webhook")
                response = requests.post(
                    self.slack_webhook_url,
                    json=slack_payload
                )
                
                # Upload the file
                logger.debug("Reading file content for upload")
                with open(self.output_file, 'r') as f:
                    file_content = f.read()
                    
                files = {
                    'file': (os.path.basename(self.output_file), file_content, 'text/markdown')
                }
                
                # Check if message was posted successfully
                if response.status_code != 200:
                    logger.warning(f"Failed to send message to Slack: {response.text}")
                else:
                    logger.info("Release notes sent to Slack successfully!")
                    
            except Exception as e:
                logger.error(f"Error sending to Slack: {e}")

def main():
    logger.info("Starting release notes generator")
    
    parser = argparse.ArgumentParser(description='Generate release notes from GitHub repositories')
    
    # GitHub settings
    parser.add_argument('-o', '--organization', default='keboola', help='GitHub organization')
    parser.add_argument('-r', '--repo', help='Generate for a single repository')
    parser.add_argument('-p', '--repo-patterns', default='component', help='Repository search patterns (comma separated)')
    parser.add_argument('--repos', help='Explicitly listed repositories (comma separated)')
    
    # Time settings
    parser.add_argument('-t', '--time-period', default='last-month', 
                        help='Time period for release notes (last-week, last-month, last-quarter, or YYYY-MM-DD-to-YYYY-MM-DD)')
    parser.add_argument('--since-last-run', action='store_true', 
                        help='Generate from the date of the last entry in the existing release notes file')
    
    # Output settings
    parser.add_argument('--template-dir', default='templates', help='Template directory')
    parser.add_argument('--output-file', default='release-notes.md', help='Output file')
    parser.add_argument('--release-notes-dir', default='release_notes', help='Directory to store individual release notes')
    parser.add_argument('--only-new-releases', action='store_true', 
                        help='Only process and send to Slack releases that haven\'t been saved before')
    
    # Feature flags
    parser.add_argument('--use-ai', action='store_true', help='Use AI to generate descriptions')
    parser.add_argument('--slack-enabled', action='store_true', help='Enable Slack notifications')
    
    # Debug
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose logging')
    
    args = parser.parse_args()
    
    if args.verbose:
        logger.setLevel(logging.DEBUG)
        logger.debug("Verbose logging enabled")
    
    try:
        logger.info(f"Using command line arguments and environment variables")
        generator = ReleaseNotesGenerator(args)
        success = generator.generate_markdown()
        
        if success:
            logger.info("Release notes generation completed successfully")
            sys.exit(0)
        else:
            logger.error("Release notes generation failed")
            sys.exit(1)
    except Exception as e:
        logger.critical(f"Unhandled exception: {e}")
        sys.exit(1)
    
if __name__ == "__main__":
    main() 