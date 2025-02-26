#!/usr/bin/env python3
import os
import sys
import yaml
import json
import argparse
import datetime
import requests
import logging
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
    def __init__(self, config_file, single_repo=None):
        """Initialize the generator with configuration."""
        logger.info(f"Initializing generator with config file: {config_file}")
        
        # Store single repo override if provided
        self.single_repo = single_repo
        if single_repo:
            logger.info(f"Single repository mode: {single_repo}")
        
        try:
            with open(config_file, 'r') as f:
                self.config = yaml.safe_load(f)
                logger.info(f"Configuration loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            raise
        
        self.github_token = self.config.get('github_token') or os.environ.get('GITHUB_TOKEN')
        if not self.github_token:
            logger.error("GitHub token is missing")
            raise ValueError("GitHub token is required. Set it in config or GITHUB_TOKEN env variable.")
        else:
            logger.info("GitHub token found")
        
        self.github = Github(self.github_token)
        self.time_period = self.config.get('time_period', 'last-month')
        logger.info(f"Time period set to: {self.time_period}")
        
        self.template_dir = self.config.get('template_dir', 'templates')
        self.output_file = self.config.get('output_file', 'release-notes.md')
        logger.info(f"Output will be written to: {self.output_file}")
        
        # AI configuration
        self.use_ai = self.config.get('use_ai', False)
        self.ai_provider = self.config.get('ai_provider', 'openai')
        self.ai_api_key = self.config.get('ai_api_key') or os.environ.get('AI_API_KEY')
        
        if self.use_ai:
            if self.ai_api_key:
                logger.info(f"AI generation enabled with provider: {self.ai_provider}")
            else:
                logger.warning("AI generation enabled but no API key provided")
        
        # Slack configuration
        self.slack_enabled = self.config.get('slack_enabled', False)
        self.slack_webhook_url = self.config.get('slack_webhook_url') or os.environ.get('SLACK_WEBHOOK_URL')
        
        if self.slack_enabled:
            if self.slack_webhook_url:
                logger.info("Slack integration enabled")
            else:
                logger.warning("Slack integration enabled but no webhook URL provided")
        
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
                    organization = self.config.get('organization')
                    if not organization:
                        logger.error(f"No organization specified in config and repository '{self.single_repo}' does not include organization")
                        return []
                    full_name = f"{organization}/{self.single_repo}"
                
                logger.info(f"Fetching repository: {full_name}")
                repos.append(self.github.get_repo(full_name))
                logger.info(f"Repository {full_name} found and added")
                return repos
            except Exception as e:
                logger.error(f"Failed to find repository {self.single_repo}: {e}")
                return []
        
        # Otherwise use configured repos
        # Get repos by pattern (containing "component")
        if self.config.get('repo_patterns'):
            for pattern in self.config['repo_patterns']:
                logger.info(f"Searching for repos with pattern: {pattern}")
                query = f"org:{self.config['organization']} {pattern} in:name"
                logger.debug(f"GitHub API query: {query}")
                
                search_results = self.github.search_repositories(query=query)
                count = 0
                for repo in search_results:
                    repos.append(repo)
                    count += 1
                
                logger.info(f"Found {count} repositories matching pattern '{pattern}'")
        
        # Get explicitly listed repos
        if self.config.get('repos'):
            logger.info(f"Adding {len(self.config['repos'])} explicitly listed repositories")
            for repo_name in self.config['repos']:
                full_name = f"{self.config['organization']}/{repo_name}"
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
            comparison = repo.compare(older_tag['commit'], newer_tag['commit'])
            logger.debug(f"Found {len(comparison.commits)} commits between tags")
            
            changes = []
            files_changed = []
            
            # Get PR information from commits
            logger.debug("Extracting PR information from commits")
            for commit in comparison.commits:
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
            
            # Get files changed
            logger.debug(f"Fetching changed files")
            for file in comparison.files:
                files_changed.append({
                    'filename': file.filename,
                    'status': file.status,
                    'additions': file.additions,
                    'deletions': file.deletions
                })
            
            logger.info(f"Comparison complete: {len(changes)} changes and {len(files_changed)} files changed")
            
            # Generate AI description if enabled
            ai_description = None
            if self.use_ai and self.ai_api_key:
                logger.info("Generating AI description for changes")
                ai_description = self.generate_ai_description(
                    repo.name, 
                    older_tag['name'], 
                    newer_tag['name'],
                    changes,
                    files_changed
                )
                    
            return {
                'changes': changes,
                'files_changed': files_changed,
                'ai_description': ai_description
            }
        except Exception as e:
            logger.error(f"Error comparing tags in {repo.name}: {e}")
            return {
                'changes': [],
                'files_changed': [],
                'ai_description': None
            }
    
    def generate_ai_description(self, repo_name, old_tag, new_tag, changes, files_changed):
        """Generate an AI-powered description of changes between tags."""
        logger.info(f"Generating AI description for {repo_name} from {old_tag} to {new_tag}")
        
        if self.ai_provider == 'openai':
            return self.generate_openai_description(repo_name, old_tag, new_tag, changes, files_changed)
        else:
            logger.warning(f"Unsupported AI provider {self.ai_provider}")
            return None
    
    def generate_openai_description(self, repo_name, old_tag, new_tag, changes, files_changed):
        """Generate a description using OpenAI."""
        try:
            if not self.ai_api_key:
                logger.warning("OpenAI API key not provided, skipping AI description")
                return None
                
            import openai
            openai.api_key = self.ai_api_key
            
            # Prepare context for the AI
            commit_messages = [change.get('title', '') for change in changes]
            files_info = [f"{f['filename']} ({f['status']}, +{f['additions']}, -{f['deletions']})" 
                        for f in files_changed[:10]]  # Limit to 10 files to avoid token limits
            
            logger.debug(f"Preparing OpenAI prompt with {len(commit_messages)} commit messages and {len(files_info)} file changes")
                        
            prompt = f"""
            Analyze these changes from {repo_name} between tags {old_tag} and {new_tag} and provide a concise summary:
            
            Commit messages:
            {json.dumps(commit_messages, indent=2)}
            
            Files changed:
            {json.dumps(files_info, indent=2)}
            
            Please provide:
            1. A short summary of the main changes (1-2 sentences)
            2. The key improvements or features added
            3. Any breaking changes or important notes
            """
            
            logger.debug("Sending request to OpenAI API")
            response = openai.Completion.create(
                model="gpt-3.5-turbo-instruct",
                prompt=prompt,
                max_tokens=300,
                temperature=0.5
            )
            
            ai_description = response.choices[0].text.strip()
            logger.info(f"AI description generated successfully ({len(ai_description)} chars)")
            return ai_description
            
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
        
        for i, repo in enumerate(repos):
            logger.info(f"Processing repository {i+1}/{len(repos)}: {repo.name}")
            
            component_name = self.get_component_name(repo)
            logger.info(f"Component name resolved to: {component_name}")
            
            tags = self.get_tags_in_period(repo, start_date, end_date)
            
            # Skip if no tags in period
            if not tags:
                logger.info(f"No tags found in date range for {repo.name}, skipping")
                continue
                
            # Get the tag before the first tag in our period (for comparison)
            logger.debug(f"Finding previous tag for comparison")
            all_tags = list(repo.get_tags())
            previous_tag_found = False
            
            for i, tag in enumerate(all_tags):
                if tag.name == tags[0]['name'] and i < len(all_tags) - 1:
                    previous_tag = {
                        'name': all_tags[i+1].name,
                        'commit': all_tags[i+1].commit.sha
                    }
                    logger.debug(f"Found previous tag: {previous_tag['name']}")
                    previous_tag_found = True
                    break
                    
            if not previous_tag_found:
                # If no previous tag, use the first commit
                logger.debug(f"No previous tag found, using initial commit")
                previous_tag = {
                    'name': 'initial',
                    'commit': list(repo.get_commits())[-1].sha
                }
            
            # Process each tag
            logger.info(f"Processing {len(tags)} tags for {repo.name}")
            for i, tag in enumerate(tags):
                logger.debug(f"Processing tag {i+1}/{len(tags)}: {tag['name']}")
                
                # Compare with previous tag or the one we found above
                compare_with = tags[i-1] if i > 0 else previous_tag
                
                change_data = self.get_changes_between_tags(repo, compare_with, tag)
                
                timeline.append({
                    'date': tag['date'],
                    'type': 'release',
                    'repo_name': repo.name,
                    'component_name': component_name,
                    'tag_name': tag['name'],
                    'tag_url': f"https://github.com/{repo.full_name}/releases/tag/{tag['name']}",
                    'changes': change_data['changes'],
                    'files_changed': change_data['files_changed'],
                    'ai_description': change_data['ai_description'],
                    'previous_tag': compare_with['name']
                })
                logger.debug(f"Added {tag['name']} to timeline with {len(change_data['changes'])} changes")
        
        # Sort timeline by date (newest first)
        logger.info(f"Sorting timeline entries (total: {len(timeline)})")
        timeline.sort(key=lambda x: x['date'], reverse=True)
        
        return timeline
    
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
    
    def send_to_slack(self, content):
        """Send release notes to Slack webhook."""
        logger.info("Preparing to send release notes to Slack")
        
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
            
            # For file upload, we need to use a different endpoint and token
            # This is a simplified example; actual implementation would depend on your Slack setup
            if self.config.get('slack_file_upload_token'):
                logger.info("Uploading file to Slack")
                upload_response = requests.post(
                    'https://slack.com/api/files.upload',
                    headers={'Authorization': f"Bearer {self.config.get('slack_file_upload_token')}"},
                    params={'channels': self.config.get('slack_channel', '')},
                    files=files
                )
                
                if not upload_response.json().get('ok'):
                    logger.warning(f"Failed to upload file to Slack: {upload_response.json().get('error')}")
                else:
                    logger.info("File uploaded to Slack successfully")
            
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
    parser.add_argument('-c', '--config', default='config.yml', help='Path to config file')
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose logging')
    parser.add_argument('-r', '--repo', help='Generate release notes for a single repository (overrides config)')
    args = parser.parse_args()
    
    if args.verbose:
        logger.setLevel(logging.DEBUG)
        logger.debug("Verbose logging enabled")
    
    try:
        logger.info(f"Using config file: {args.config}")
        generator = ReleaseNotesGenerator(args.config, single_repo=args.repo)
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