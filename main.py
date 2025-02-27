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
from openai import OpenAI

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
        
        # OpenAI configuration
        self.openai_api_key = os.environ.get('OPENAI_API_KEY')
        self.openai_client = None
        if args.ai_summary and self.openai_api_key:
            self.openai_client = OpenAI(api_key=self.openai_api_key)
            logger.info("OpenAI API initialized")
        elif args.ai_summary and not self.openai_api_key:
            logger.warning("AI summaries requested but no OPENAI_API_KEY provided - AI descriptions will be disabled")
        
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
                logger.info("No previous release notes found, using last 30 days")
                today = datetime.datetime.now().strftime('%Y-%m-%d')
                thirty_days_ago = (datetime.datetime.now() - datetime.timedelta(days=30)).strftime('%Y-%m-%d')
                return f"{thirty_days_ago}-to-{today}"
            
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
            # Default to last 30 days if there's an error
            today = datetime.datetime.now().strftime('%Y-%m-%d')
            thirty_days_ago = (datetime.datetime.now() - datetime.timedelta(days=30)).strftime('%Y-%m-%d')
            return f"{thirty_days_ago}-to-{today}"
        
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
            # Make end_date the end of the day (23:59:59)
            end_date = end_date.replace(hour=23, minute=59, second=59, tzinfo=datetime.timezone.utc)
            return start_date, end_date
        else:
            # Default to last 30 days
            start_date = today - datetime.timedelta(days=30)
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
            # Get a reasonable number of recent tags (100) instead of all tags
            # This is still much faster than getting all tags
            recent_tags = list(repo.get_tags())[:100]
            logger.info(f"Retrieved {len(recent_tags)} recent tags from {repo.name}")
            
            # Filter tags by date directly
            for tag in recent_tags:
                try:
                    commit_date = tag.commit.commit.author.date
                    
                    # Make sure we're comparing timezone-aware dates consistently
                    if commit_date.tzinfo is None:
                        commit_date = commit_date.replace(tzinfo=datetime.timezone.utc)
                    
                    # Check if date is in our range
                    if start_date <= commit_date <= end_date:
                        tags.append({
                            'name': tag.name,
                            'date': commit_date,
                            'commit': tag.commit.sha,
                            'message': tag.commit.commit.message,
                            'url': tag.commit.html_url
                        })
                except Exception as tag_e:
                    logger.warning(f"Error processing tag {tag.name}: {tag_e}")
                    continue
            
            logger.info(f"Found {len(tags)} tags in {repo.name} within date range {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
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
            
            # Generate AI description for the changes
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
            
            # Get tags within date range - optimized method
            tags = self.get_tags_in_period(repo, start_date, end_date)
            
            # Skip if no tags in period
            if not tags:
                continue
            
            # Check which tags have already been processed
            tags_to_process = []
            for tag in tags:
                # Check if we've already processed this release
                timestamp = tag['date'].strftime('%Y-%m-%d-%H-%M-%S')
                component_name_normalized = component_name.replace('.', '-').replace(' ', '-').lower()
                file_name = f"{timestamp}_{tag['name']}_{component_name_normalized}.md"
                file_path = os.path.join(RELEASE_NOTES_DIR, file_name)
                
                # Skip if file already exists
                if os.path.exists(file_path):
                    continue
                
                tags_to_process.append(tag)
            
            logger.info(f"Found {len(tags_to_process)} new tags to process in {repo.name}")
            
            # Process each new tag
            for tag in tags_to_process:
                # Find the previous tag - we'll use tag date to find chronologically previous tag
                try:
                    # Get just the one tag before our current one by date
                    all_tags = list(repo.get_tags())[:50]  # Limit to 50 recent tags for efficiency
                    sorted_tags = sorted(all_tags, key=lambda t: t.commit.commit.author.date)
                    
                    tag_date = tag['date']
                    previous_tag = None
                    
                    for t in sorted_tags:
                        t_date = t.commit.commit.author.date
                        if t_date.tzinfo is None:
                            t_date = t_date.replace(tzinfo=datetime.timezone.utc)
                        
                        if t_date < tag_date and t.name != tag['name']:
                            previous_tag = {
                                'name': t.name,
                                'commit': t.commit.sha,
                                'date': t_date,
                                'message': t.commit.commit.message,
                                'url': t.commit.html_url
                            }
                            break
                    
                    # If no previous tag found, use the initial commit
                    if not previous_tag:
                        initial_commit = list(repo.get_commits().reversed())[-1]
                        previous_tag = {
                            'name': 'initial',
                            'commit': initial_commit.sha,
                            'date': initial_commit.commit.author.date,
                            'message': initial_commit.commit.message,
                            'url': initial_commit.html_url
                        }
                except Exception as e:
                    logger.error(f"Error finding previous tag: {e}")
                    # Use first commit as fallback
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
                        # Last resort fallback
                        previous_date = tag['date'] - datetime.timedelta(days=1)
                        previous_tag = {
                            'name': 'initial',
                            'commit': tag['commit'],
                            'date': previous_date,
                            'message': 'Initial state',
                            'url': tag['url']
                        }
                
                # Get changes between tags
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
                    'ai_description': change_data['ai_description'],
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

    def generate_ai_description(self, repo_name, previous_tag, current_tag, changes):
        """Generate an AI description of the changes between tags."""
        if not self.openai_client:
            return None
            
        try:
            # Format the changes as a readable list
            changes_list = ""
            for change in changes:
                if 'title' in change:
                    changes_list += f"- {change['title']}\n"
            
            # Create the prompt
            prompt = f"""
            Summarize the following changes in the {repo_name} repository between tags {previous_tag} and {current_tag}:
            
            {changes_list}
            
            Provide a concise technical summary focusing on the most significant changes.
            Focus on what was changed, added, fixed, or improved. Keep it under 150 words.
            """
            
            # Make the API call
            response = self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a technical writer summarizing software changes."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=300,
                temperature=0.5
            )
            
            # Extract and return the AI description
            ai_description = response.choices[0].message.content.strip()
            logger.info(f"Generated AI description for {repo_name} {current_tag}")
            return ai_description
            
        except Exception as e:
            logger.error(f"Error generating AI description: {e}")
            return None

def main():
    logger.info("Starting release notes generator")
    
    parser = argparse.ArgumentParser(description='Generate release notes from GitHub repositories')
    
    # Simplified command line options
    parser.add_argument('--since-last-run', action='store_true', 
                        help='Generate from the date of the last release note file')
    parser.add_argument('--slack', action='store_true', help='Enable Slack notifications')
    parser.add_argument('--ai-summary', action='store_true', help='Generate AI summary of changes (requires OPENAI_API_KEY)')
    
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