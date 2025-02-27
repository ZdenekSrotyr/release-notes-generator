#!/usr/bin/env python3
import os
import datetime

from src.config import logger
from src.github_utils import initialize_github_client, get_repositories, get_tags_in_period, get_changes_between_tags, \
    fix_timezone, get_repo_tags
from src.component_utils import get_component_name, load_component_details, determine_component_stage
from src.template_utils import detect_time_period_from_last_run, save_component_release_note
from src.ai_utils import initialize_openai_client, generate_ai_description
from src.slack_utils import send_slack_notification


class ReleaseNotesGenerator:
    """Main class for generating release notes."""

    def __init__(self, github_token, start_date=None, end_date=None, organization="keboola"):
        """Initialize generator with GitHub token and date range."""
        # Initialize GitHub client
        self.github = initialize_github_client(github_token)
        self.organization = organization

        # Determine time period
        if start_date and end_date:
            # If explicit dates provided, use them
            self.start_date = start_date
            self.end_date = end_date
            logger.info(
                f"Using specified date range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
        else:
            # Detect from last run or use default of 30 days
            self.start_date, self.end_date = detect_time_period_from_last_run(days=30)
            logger.info(
                f"Using date range: {self.start_date.strftime('%Y-%m-%d')} to {self.end_date.strftime('%Y-%m-%d')}")

        # Initialize OpenAI client - will be None if API key is not available
        self.openai_client = initialize_openai_client()

        # Initialize tracking for new releases
        self.new_releases = []

    def find_previous_tag(self, repo, tag, all_tags):
        """Find the chronologically previous tag to the given tag."""
        try:
            tag_date = tag['date']

            # Sort tags by date
            sorted_tags = sorted(all_tags, key=lambda t: t['date'])

            # Find the most recent tag that's older than our current tag
            for t in sorted_tags:
                if t['date'] < tag_date and t['name'] != tag['name']:
                    return t

            # If no previous tag found, use the initial commit
            try:
                commits = list(repo.get_commits(sha=repo.default_branch).reversed)
                if commits:
                    initial_commit = commits[0]
                    return {
                        'name': 'initial',
                        'commit': initial_commit.sha,
                        'date': fix_timezone(initial_commit.commit.author.date),
                        'message': initial_commit.commit.message,
                        'url': initial_commit.html_url
                    }
            except Exception as e:
                logger.warning(f"Error finding initial commit: {e}")

            # Fallback if we can't get commits
            previous_date = tag_date - datetime.timedelta(days=1)
            return {
                'name': 'initial',
                'commit': tag['commit'],
                'date': previous_date,
                'message': 'Initial state',
                'url': tag['url']
            }

        except Exception as e:
            logger.error(f"Error finding previous tag: {e}")

            # Last resort fallback
            previous_date = tag['date'] - datetime.timedelta(days=1)
            return {
                'name': 'initial',
                'commit': tag['commit'],
                'date': previous_date,
                'message': 'Initial state',
                'url': tag['url']
            }

    def process_component_tag(self, repo, component, tag, all_tags):
        """Process a specific tag for a component."""
        component_name = component['name']
        component_details = component['details']
        component_stage = component['stage']

        # Find the previous tag
        previous_tag = self.find_previous_tag(repo, tag, all_tags)

        # Get changes between tags
        change_data = get_changes_between_tags(repo, previous_tag, tag)

        # Generate AI description if enabled
        ai_description = None
        if self.openai_client and change_data['changes']:
            ai_description = generate_ai_description(
                self.openai_client,
                repo.name,
                previous_tag['name'],
                tag['name'],
                change_data['changes']
            )
            # If ai_description failed and returned None, disable the client for future tags
            if ai_description is None and self.openai_client is not None:
                logger.info("AI description generation failed - disabling for subsequent tags")
                self.openai_client = None

        # Add the AI description to the change data
        change_data['ai_description'] = ai_description

        # Create entry for this release
        entry = {
            'date': tag['date'],
            'type': 'release',
            'repo_name': repo.name,
            'component_name': component_name,
            'component_details': component_details,
            'tag_name': tag['name'],
            'tag_url': f"https://github.com/{repo.full_name}/releases/tag/{tag['name']}",
            'changes': change_data['changes'],
            'ai_description': change_data['ai_description'],
            'previous_tag': previous_tag['name'],
            'component_stage': component_stage
        }

        return entry, previous_tag

    def generate_timeline(self):
        """Generate a timeline of all changes across repositories."""
        logger.info("Generating timeline of changes")
        repos = get_repositories(self.github, self.organization)
        components_details = load_component_details()

        # Timeline will be a list of events
        timeline = []
        new_releases = []  # Track new releases for Slack notification

        for repo in repos:
            component_names = get_component_name(repo)
            logger.info(f"Found component names for {repo.name}: {component_names}")

            # First check if any component exists in components_details
            valid_components = []
            for component_name in component_names:
                matched_component = next((c for c in components_details if c.get('id') == component_name), None)
                if matched_component:
                    component_stage = determine_component_stage(matched_component)
                    logger.info(f"Component {component_name} is in {component_stage} stage")
                    valid_components.append({
                        'name': component_name,
                        'details': matched_component,
                        'stage': component_stage
                    })
                else:
                    logger.info(f"No details found for component {component_name}, skipping")

            # If no valid components found, skip this repository
            if not valid_components:
                logger.info(f"No valid components found for repository {repo.name}, skipping")
                continue

            # Only now get tags since we have at least one valid component
            tags = get_tags_in_period(repo, self.start_date, self.end_date)

            # Skip if no tags in period
            if not tags:
                logger.info(f"No tags found for {repo.name} in the specified period")
                continue

            # Get all tags for this repo (for finding previous tags)
            all_tags = get_repo_tags(repo)

            # Process each valid component found
            for component in valid_components:
                component_name = component['name']

                # Check which tags have already been processed
                tags_to_process = []
                for tag in tags:
                    # Check if we've already processed this release
                    timestamp = tag['date'].strftime('%Y-%m-%d-%H-%M-%S')
                    component_name_normalized = component_name.replace('.', '-').replace(' ', '-').lower()
                    stage = component['stage'].lower()
                    file_name = f"{timestamp}_{stage}_{tag['name']}_{component_name_normalized}.md"
                    file_path = os.path.join("release_notes", file_name)

                    # Skip if file already exists
                    if os.path.exists(file_path):
                        continue

                    tags_to_process.append(tag)

                logger.info(f"Found {len(tags_to_process)} new tags to process for component {component_name}")

                # Process each new tag
                for tag in tags_to_process:
                    # Process component tag
                    entry, previous_tag = self.process_component_tag(repo, component, tag, all_tags)

                    # Save individual release note
                    is_new = save_component_release_note(entry)
                    if is_new:
                        new_releases.append(entry)

                    # Add to timeline for main release notes
                    timeline.append(entry)

        # Sort timeline by date (newest first)
        timeline.sort(key=lambda x: x['date'], reverse=True)

        # Save the list of new releases for Slack notification
        self.new_releases = new_releases

        return timeline

    def send_slack_notification(self):
        """Send notification to Slack about new releases."""
        return send_slack_notification(self.new_releases)
