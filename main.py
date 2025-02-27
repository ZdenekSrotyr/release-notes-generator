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

# Constants
GITHUB_ORGANIZATION = "keboola"
REPO_PATTERNS = "component"
TEMPLATE_DIR = "templates"
RELEASE_NOTES_DIR = "release_notes"

# Configure simple logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('release-notes-generator')

class ReleaseNotesGenerator:
    def __init__(self, args):
        """Initialize the generator with arguments."""
        logger.info("Initializing generator")
        
        # Store command line arguments
        self.args = args
        
        # GitHub configuration
        self.github_token = os.environ.get('GITHUB_TOKEN')
        if not self.github_token:
            raise ValueError("GitHub token is required. Set GITHUB_TOKEN env variable.")
        
        self.github = Github(self.github_token)
        self.organization = GITHUB_ORGANIZATION
        
        # Time period configuration - only since last run or last day
        if args.since_last_run:
            self.time_period = self._detect_time_period_from_last_run()
        else:
            # Default to last day for initial run
            today = datetime.datetime.now().strftime('%Y-%m-%d')
            yesterday = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime('%Y-%m-%d')
            self.time_period = f"{yesterday}-to-{today}"
        
        # Ensure release notes directory exists
        os.makedirs(RELEASE_NOTES_DIR, exist_ok=True)
        
        # Slack configuration
        self.slack_enabled = args.slack
        self.slack_webhook_url = os.environ.get('SLACK_WEBHOOK_URL')
        
        if self.slack_enabled and not self.slack_webhook_url:
            logger.warning("Slack enabled but no webhook URL provided - disabling Slack")
            self.slack_enabled = False
    
    def _detect_time_period_from_last_run(self):
        """Detect time period by finding the latest release notes file."""
        try:
            # Get the list of all release notes files
            files = glob.glob(f"{RELEASE_NOTES_DIR}/*.md")
            
            if not files:
                logger.info("No previous release notes found, using last day")
                today = datetime.datetime.now().strftime('%Y-%m-%d')
                yesterday = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime('%Y-%m-%d')
                return f"{yesterday}-to-{today}"
            
            # Get the latest file by timestamp in filename
            latest_file = max(files, key=os.path.getctime)
            filename = os.path.basename(latest_file)
            
            # Extract the timestamp from the filename (YYYY-MM-DD-HH-MM-SS_tag_component-name.md)
            timestamp_str = filename.split('_')[0]
            
            # Parse the timestamp
            timestamp = datetime.datetime.strptime(timestamp_str, '%Y-%m-%d-%H-%M-%S')
            
            # Create time period from that timestamp to now
            latest_date = timestamp.strftime('%Y-%m-%d')
            today = datetime.datetime.now().strftime('%Y-%m-%d')
            
            # If the latest date is today, we still want to include today
            time_period = f"{latest_date}-to-{today}"
            logger.info(f"Using time period: {time_period}")
            
            return time_period
            
        except Exception as e:
            logger.error(f"Error detecting time period from last run: {e}")
            # Default to last day if there's an error
            today = datetime.datetime.now().strftime('%Y-%m-%d')
            yesterday = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime('%Y-%m-%d')
            return f"{yesterday}-to-{today}"
        
    def get_date_range(self):
        """Convert time period to actual dates."""
        today = datetime.datetime.now(datetime.timezone.utc)  # Use UTC timezone-aware datetime
        
        if '-to-' in self.time_period:
            # Handle custom date range like "2023-01-01-to-2023-02-01"
            start_str, end_str = self.time_period.split('-to-')
            start_date = datetime.datetime.strptime(start_str, '%Y-%m-%d')
            end_date = datetime.datetime.strptime(end_str, '%Y-%m-%d')
            # Make them timezone-aware with UTC
            start_date = start_date.replace(tzinfo=datetime.timezone.utc)
            end_date = end_date.replace(tzinfo=datetime.timezone.utc)
            return start_date, end_date
        else:
            # Default to last day
            start_date = today - datetime.timedelta(days=1)
            return start_date, today
        
    def get_repos(self):
        """Get list of repositories based on pattern."""
        logger.info("Finding repositories...")
        repos = []
        
        # Get repos by pattern
        for pattern in REPO_PATTERNS.split(','):
            query = f"org:{self.organization} {pattern} in:name"
            search_results = self.github.search_repositories(query=query)
            for repo in search_results:
                repos.append(repo)
        
        logger.info(f"Found {len(repos)} repositories to process")
        return repos
    
    def get_component_name(self, repo):
        """Extract component name from workflow file."""
        try:
            workflow_path = ".github/workflows/push.yml"
            workflow_content = repo.get_contents(workflow_path).decoded_content.decode('utf-8')
            workflow_yaml = yaml.safe_load(workflow_content)
            
            # Look for KBC_DEVELOPERPORTAL_APP in env section
            if 'env' in workflow_yaml:
                component_name = workflow_yaml['env'].get('KBC_DEVELOPERPORTAL_APP', repo.name)
                if component_name != repo.name:
                    return component_name
            
            # Try to find it in jobs
            for job_name, job in workflow_yaml.get('jobs', {}).items():
                if 'env' in job and 'KBC_DEVELOPERPORTAL_APP' in job['env']:
                    component_name = job['env']['KBC_DEVELOPERPORTAL_APP']
                    return component_name
            
            # Default to repo name if not found
            return repo.name
        except Exception:
            return repo.name
        
    def get_tags_in_period(self, repo, start_date, end_date):
        """Get tags created in the specified period."""
        logger.info(f"Retrieving tags for {repo.name}")
        tags = []
        
        try:
            all_tags = list(repo.get_tags())
            
            for tag in all_tags:
                # Get the commit date
                commit = tag.commit
                commit_date = commit.commit.author.date
                
                # Make sure we're comparing timezone-aware dates consistently
                if commit_date.tzinfo is None:
                    commit_date = commit_date.replace(tzinfo=datetime.timezone.utc)
                
                if start_date <= commit_date <= end_date:
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
        logger.info(f"Comparing {older_tag['name']} and {newer_tag['name']} in {repo.name}")
        
        try:
            comparison = repo.compare(older_tag['commit'], newer_tag['commit'])
            commits_list = list(comparison.commits)
            
            changes = []
            
            # Get PR information from commits
            for commit in commits_list:
                # Extract PR number from commit message if available
                pr_number = None
                message = commit.commit.message
                if '(#' in message:
                    pr_part = message.split('(#')[1]
                    if ')' in pr_part:
                        pr_number = pr_part.split(')')[0]
                
                if pr_number:
                    try:
                        pr = repo.get_pull(int(pr_number))
                        changes.append({
                            'title': pr.title,
                            'number': pr.number,
                            'url': pr.html_url,
                            'body': pr.body,
                            'merged_at': pr.merged_at
                        })
                    except Exception:
                        # If PR can't be found, use commit info
                        changes.append({
                            'title': commit.commit.message.split('\n')[0],
                            'commit': commit.sha,
                            'url': commit.html_url
                        })
                else:
                    changes.append({
                        'title': commit.commit.message.split('\n')[0],
                        'commit': commit.sha,
                        'url': commit.html_url
                    })
            
            return {
                'changes': changes,
                'ai_description': None  # Removed AI description for simplicity
            }
        except Exception as e:
            logger.error(f"Error comparing tags in {repo.name}: {e}")
            return {
                'changes': [],
                'ai_description': None
            }
    
    def generate_timeline(self):
        """Generate a timeline of all changes across repositories."""
        logger.info("Generating timeline of changes")
        start_date, end_date = self.get_date_range()
        repos = self.get_repos()
        
        # Timeline will be a list of events
        timeline = []
        new_releases = []  # Track new releases for Slack notification
        
        for repo in repos:
            component_name = self.get_component_name(repo)
            
            # Get all tags and sort them by date
            try:
                all_repo_tags = []
                all_tags_api = list(repo.get_tags())
                
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
                    except Exception:
                        pass
                
                # Sort all tags chronologically (oldest first)
                all_repo_tags = sorted(all_repo_tags, key=lambda x: x['date'])
                
                # Filter tags in specified period
                tags = []
                for tag in all_repo_tags:
                    # Check if we should only process new releases
                    timestamp = tag['date'].strftime('%Y-%m-%d-%H-%M-%S')
                    component_name_normalized = component_name.replace('.', '-').replace(' ', '-').lower()
                    file_name = f"{timestamp}_{tag['name']}_{component_name_normalized}.md"
                    file_path = os.path.join(RELEASE_NOTES_DIR, file_name)
                    
                    # Skip if file already exists
                    if os.path.exists(file_path):
                        continue
                    
                    if start_date <= tag['date'] <= end_date:
                        tags.append(tag)
                
                logger.info(f"Found {len(tags)} new tags in {repo.name} within date range")
            except Exception:
                continue
            
            # Skip if no tags in period
            if not tags:
                continue
                
            # Process each tag
            for i, tag in enumerate(tags):
                # Find the previous tag in the chronological order
                previous_tag = None
                
                if i > 0:
                    # Use the previous tag in our period
                    previous_tag = tags[i-1]
                else:
                    # Find the tag that immediately precedes the first tag in our period
                    tag_index = all_repo_tags.index(tag)
                    if tag_index > 0:
                        previous_tag = all_repo_tags[tag_index - 1]
                    else:
                        # If this is the first tag ever, use the initial commit
                        try:
                            initial_commit = list(repo.get_commits().reversed())[-1]
                            previous_tag = {
                                'name': 'initial',
                                'commit': initial_commit.sha,
                                'date': initial_commit.commit.author.date,
                                'message': initial_commit.commit.message,
                                'url': initial_commit.html_url
                            }
                        except Exception:
                            # Use tag's own commit but from 1 day before as a fallback
                            previous_date = tag['date'] - datetime.timedelta(days=1)
                            previous_tag = {
                                'name': 'initial',
                                'commit': tag['commit'],
                                'date': previous_date,
                                'message': 'Initial state',
                                'url': tag['url']
                            }
                
                # Ensure older_tag is chronologically before newer_tag
                if previous_tag['date'] > tag['date']:
                    change_data = self.get_changes_between_tags(repo, tag, previous_tag)
                else:
                    change_data = self.get_changes_between_tags(repo, previous_tag, tag)
                
                # Create entry for this release
                entry = {
                    'date': tag['date'],
                    'type': 'release',
                    'repo_name': repo.name,
                    'component_name': component_name,
                    'tag_name': tag['name'],
                    'tag_url': f"https://github.com/{repo.full_name}/releases/tag/{tag['name']}",
                    'changes': change_data['changes'],
                    'ai_description': None,  # No AI description
                    'previous_tag': previous_tag['name']
                }
                
                # Save individual release note
                is_new = self.save_component_release_note(entry)
                if is_new:
                    new_releases.append(entry)
                
                # Add to timeline for main release notes
                timeline.append(entry)
        
        # Sort timeline by date (newest first)
        timeline.sort(key=lambda x: x['date'], reverse=True)
        
        # Save the list of new releases for Slack notification
        self.new_releases = new_releases
        
        return timeline
    
    def save_component_release_note(self, entry):
        """Save a release note for a single component release."""
        # Format: YYYY-MM-DD-HH-MM-SS_tag_component-name.md
        timestamp = entry['date'].strftime('%Y-%m-%d-%H-%M-%S')
        component_name = entry['component_name'].replace('.', '-').replace(' ', '-').lower()
        tag_name = entry['tag_name']
        file_name = f"{timestamp}_{tag_name}_{component_name}.md"
        file_path = os.path.join(RELEASE_NOTES_DIR, file_name)
        
        # Check if this release note already exists
        if os.path.exists(file_path):
            return False
        
        # Create the release note content
        template_loader = FileSystemLoader(TEMPLATE_DIR)
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
    
    def run(self):
        """Run the generator to create individual release notes files."""
        try:
            timeline = self.generate_timeline()
            logger.info(f"Generated {len(timeline)} release notes")
            
            # Send to Slack if enabled
            if self.slack_enabled and self.slack_webhook_url and hasattr(self, 'new_releases'):
                if self.new_releases:
                    self.send_to_slack()
                else:
                    logger.info("No new releases to send to Slack")
            
            return True
        except Exception as e:
            logger.error(f"Error generating release notes: {e}")
            return False
    
    def send_to_slack(self):
        """Send new release notes to Slack webhook."""
        logger.info(f"Sending {len(self.new_releases)} new releases to Slack")
        
        try:
            # Create a list of components updated
            components_updated = []
            summary_text = ""
            
            for entry in self.new_releases:
                component = entry['component_name']
                tag = entry['tag_name']
                components_updated.append(f"*{component}* {tag}")
                
                # Add a summary for this component
                summary_text += f"*{component}* {tag} - {entry['date'].strftime('%Y-%m-%d')}:\n"
                
                # Add a few changes
                if entry['changes']:
                    for i, change in enumerate(entry['changes'][:3]):
                        summary_text += f"• {change['title']}\n"
                    if len(entry['changes']) > 3:
                        summary_text += f"_...and {len(entry['changes']) - 3} more changes_\n"
                
                summary_text += f"<{entry['tag_url']}|View on GitHub>\n\n"
            
            # Format content for Slack
            title = f"*New Release Notes*\n\n"
            
            # Prepare the payload
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

def main():
    logger.info("Starting release notes generator")
    
    parser = argparse.ArgumentParser(description='Generate release notes from GitHub repositories')
    
    # Simplified command line options
    parser.add_argument('--since-last-run', action='store_true', 
                        help='Generate from the date of the last release note file')
    parser.add_argument('--slack', action='store_true', help='Enable Slack notifications')
    
    args = parser.parse_args()
    
    try:
        generator = ReleaseNotesGenerator(args)
        success = generator.run()
        
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