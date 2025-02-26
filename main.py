#!/usr/bin/env python3
import os
import sys
import yaml
import json
import argparse
import datetime
import requests
from github import Github
from jinja2 import Environment, FileSystemLoader

class ReleaseNotesGenerator:
    def __init__(self, config_file):
        """Initialize the generator with configuration."""
        with open(config_file, 'r') as f:
            self.config = yaml.safe_load(f)
        
        self.github_token = self.config.get('github_token') or os.environ.get('GITHUB_TOKEN')
        if not self.github_token:
            raise ValueError("GitHub token is required. Set it in config or GITHUB_TOKEN env variable.")
        
        self.github = Github(self.github_token)
        self.time_period = self.config.get('time_period', 'last-month')
        self.template_dir = self.config.get('template_dir', 'templates')
        self.output_file = self.config.get('output_file', 'release-notes.md')
        
        # AI configuration
        self.use_ai = self.config.get('use_ai', False)
        self.ai_provider = self.config.get('ai_provider', 'openai')
        self.ai_api_key = self.config.get('ai_api_key') or os.environ.get('AI_API_KEY')
        
        # Slack configuration
        self.slack_enabled = self.config.get('slack_enabled', False)
        self.slack_webhook_url = self.config.get('slack_webhook_url') or os.environ.get('SLACK_WEBHOOK_URL')
        
    def get_date_range(self):
        """Convert time period to actual dates."""
        today = datetime.datetime.now(datetime.timezone.utc)  # Use UTC timezone-aware datetime
        
        if self.time_period == 'last-week':
            start_date = today - datetime.timedelta(days=7)
        elif self.time_period == 'last-month':
            start_date = today - datetime.timedelta(days=30)
        elif self.time_period == 'last-quarter':
            start_date = today - datetime.timedelta(days=90)
        elif '-to-' in self.time_period:
            # Handle custom date range like "2023-01-01-to-2023-02-01"
            start_str, end_str = self.time_period.split('-to-')
            start_date = datetime.datetime.strptime(start_str, '%Y-%m-%d')
            end_date = datetime.datetime.strptime(end_str, '%Y-%m-%d')
            # Make them timezone-aware with UTC
            start_date = start_date.replace(tzinfo=datetime.timezone.utc)
            end_date = end_date.replace(tzinfo=datetime.timezone.utc)
            return start_date, end_date
        else:
            # Default to last month
            start_date = today - datetime.timedelta(days=30)
            
        return start_date, today
        
    def get_repos(self):
        """Get list of repositories based on configuration."""
        repos = []
        
        # Get repos by pattern (containing "component")
        if self.config.get('repo_patterns'):
            for pattern in self.config['repo_patterns']:
                for repo in self.github.search_repositories(query=f"org:{self.config['organization']} {pattern} in:name"):
                    repos.append(repo)
        
        # Get explicitly listed repos
        if self.config.get('repos'):
            for repo_name in self.config['repos']:
                full_name = f"{self.config['organization']}/{repo_name}"
                repos.append(self.github.get_repo(full_name))
                
        return repos
    
    def get_component_name(self, repo):
        """Extract component name from workflow file."""
        try:
            workflow_content = repo.get_contents(".github/workflows/push.yml").decoded_content.decode('utf-8')
            workflow_yaml = yaml.safe_load(workflow_content)
            
            # Look for KBC_DEVELOPERPORTAL_APP in env section
            if 'env' in workflow_yaml:
                return workflow_yaml['env'].get('KBC_DEVELOPERPORTAL_APP', repo.name)
            
            # Try to find it in jobs
            for job in workflow_yaml.get('jobs', {}).values():
                if 'env' in job and 'KBC_DEVELOPERPORTAL_APP' in job['env']:
                    return job['env']['KBC_DEVELOPERPORTAL_APP']
            
            # Default to repo name if not found
            return repo.name
        except Exception as e:
            print(f"Warning: Could not extract component name for {repo.name}: {e}")
            return repo.name
        
    def get_tags_in_period(self, repo, start_date, end_date):
        """Get tags created in the specified period."""
        tags = []
        for tag in repo.get_tags():
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
        
        return sorted(tags, key=lambda x: x['date'])
        
    def get_changes_between_tags(self, repo, older_tag, newer_tag):
        """Get changes between two tags."""
        comparison = repo.compare(older_tag['commit'], newer_tag['commit'])
        
        changes = []
        files_changed = []
        
        # Get PR information from commits
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
                    pr = repo.get_pull(int(pr_number))
                    changes.append({
                        'title': pr.title,
                        'number': pr.number,
                        'url': pr.html_url,
                        'body': pr.body,
                        'merged_at': pr.merged_at
                    })
                except:
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
        
        # Get files changed
        for file in comparison.files:
            files_changed.append({
                'filename': file.filename,
                'status': file.status,
                'additions': file.additions,
                'deletions': file.deletions
            })
        
        # Generate AI description if enabled
        ai_description = None
        if self.use_ai and self.ai_api_key:
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
    
    def generate_ai_description(self, repo_name, old_tag, new_tag, changes, files_changed):
        """Generate an AI-powered description of changes between tags."""
        if self.ai_provider == 'openai':
            return self.generate_openai_description(repo_name, old_tag, new_tag, changes, files_changed)
        else:
            print(f"Warning: Unsupported AI provider {self.ai_provider}")
            return None
    
    def generate_openai_description(self, repo_name, old_tag, new_tag, changes, files_changed):
        """Generate a description using OpenAI."""
        try:
            if not self.ai_api_key:
                print("Warning: OpenAI API key not provided, skipping AI description")
                return None
                
            import openai
            openai.api_key = self.ai_api_key
            
            # Prepare context for the AI
            commit_messages = [change.get('title', '') for change in changes]
            files_info = [f"{f['filename']} ({f['status']}, +{f['additions']}, -{f['deletions']})" 
                        for f in files_changed[:10]]  # Limit to 10 files to avoid token limits
                        
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
            
            response = openai.Completion.create(
                model="gpt-3.5-turbo-instruct",
                prompt=prompt,
                max_tokens=300,
                temperature=0.5
            )
            
            return response.choices[0].text.strip()
            
        except Exception as e:
            print(f"Error generating AI description: {e}")
            return None
    
    def generate_timeline(self):
        """Generate a timeline of all changes across repositories."""
        start_date, end_date = self.get_date_range()
        repos = self.get_repos()
        
        # Timeline will be a list of events
        timeline = []
        
        for repo in repos:
            component_name = self.get_component_name(repo)
            tags = self.get_tags_in_period(repo, start_date, end_date)
            
            # Skip if no tags in period
            if not tags:
                continue
                
            # Get the tag before the first tag in our period (for comparison)
            all_tags = list(repo.get_tags())
            for i, tag in enumerate(all_tags):
                if tag.name == tags[0]['name'] and i < len(all_tags) - 1:
                    previous_tag = {
                        'name': all_tags[i+1].name,
                        'commit': all_tags[i+1].commit.sha
                    }
                    break
            else:
                # If no previous tag, use the first commit
                previous_tag = {
                    'name': 'initial',
                    'commit': list(repo.get_commits())[-1].sha
                }
            
            # Process each tag
            for i, tag in enumerate(tags):
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
        
        # Sort timeline by date (newest first)
        timeline.sort(key=lambda x: x['date'], reverse=True)
        
        return timeline
    
    def generate_markdown(self):
        """Generate markdown content."""
        timeline = self.generate_timeline()
        env = Environment(loader=FileSystemLoader(self.template_dir))
        template = env.get_template('release-notes.md.j2')
        
        content = template.render(
            timeline=timeline,
            generated_at=datetime.datetime.now(datetime.timezone.utc),  # Use UTC timezone-aware datetime
            time_period=self.time_period
        )
        
        with open(self.output_file, 'w') as f:
            f.write(content)
            
        print(f"Release notes generated successfully in {self.output_file}")
        
        # Send to Slack if enabled
        if self.slack_enabled and self.slack_webhook_url:
            self.send_to_slack(content)
    
    def send_to_slack(self, content):
        """Send release notes to Slack webhook."""
        try:
            # Format content for Slack
            # Create a simple summary for Slack
            summary = f"*Release Notes for {self.time_period}*\n\n"
            
            # Add a summary of components updated
            components_updated = set()
            for entry in self.generate_timeline():
                components_updated.add(entry['component_name'])
            
            summary += f"*Components updated:* {', '.join(sorted(components_updated))}\n\n"
            summary += f"*Details:* See the attached file for complete release notes."
            
            # Prepare the payload
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
            response = requests.post(
                self.slack_webhook_url,
                json=slack_payload
            )
            
            # Upload the file
            with open(self.output_file, 'r') as f:
                file_content = f.read()
                
            files = {
                'file': (os.path.basename(self.output_file), file_content, 'text/markdown')
            }
            
            # For file upload, we need to use a different endpoint and token
            # This is a simplified example; actual implementation would depend on your Slack setup
            if self.config.get('slack_file_upload_token'):
                upload_response = requests.post(
                    'https://slack.com/api/files.upload',
                    headers={'Authorization': f"Bearer {self.config.get('slack_file_upload_token')}"},
                    params={'channels': self.config.get('slack_channel', '')},
                    files=files
                )
                
                if not upload_response.json().get('ok'):
                    print(f"Warning: Failed to upload file to Slack: {upload_response.json().get('error')}")
            
            # Check if message was posted successfully
            if response.status_code != 200:
                print(f"Warning: Failed to send message to Slack: {response.text}")
            else:
                print("Release notes sent to Slack successfully!")
                
        except Exception as e:
            print(f"Error sending to Slack: {e}")
        
def main():
    parser = argparse.ArgumentParser(description='Generate release notes from GitHub repositories')
    parser.add_argument('-c', '--config', default='config.yml', help='Path to config file')
    args = parser.parse_args()
    
    generator = ReleaseNotesGenerator(args.config)
    generator.generate_markdown()
    
if __name__ == "__main__":
    main() 