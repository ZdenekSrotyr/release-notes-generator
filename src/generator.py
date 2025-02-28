#!/usr/bin/env python3
import os
import datetime
import concurrent.futures
from typing import Any
import re

from src.config import logger
from src.github_utils import initialize_github_client, get_repositories, get_tags_in_period, get_changes_between_tags, \
    fix_timezone, get_repo_tags
from src.component_utils import get_component_name, load_component_details, determine_component_stage
from src.template_utils import detect_time_period_from_last_run, save_component_release_note
from src.ai_utils import initialize_openai_client, generate_ai_description


class ReleaseNotesGenerator:
    """Main class for generating release notes."""

    def __init__(self, github_token):
        """Initialize generator with GitHub token."""
        # Initialize GitHub client
        self.github = initialize_github_client(github_token, )
        self.organization = "keboola"  # Organization is set as a constant

        # Detect time period from last run or use default of 30 days
        self.start_date, self.end_date = detect_time_period_from_last_run(days=30)
        logger.info(
            f"Using date range: {self.start_date.strftime('%Y-%m-%d')} to {self.end_date.strftime('%Y-%m-%d')}")

        # Initialize OpenAI client - will be None if API key is not available
        self.openai_client = initialize_openai_client()

        # Initialize tracking for new releases
        self.new_releases = []

    def find_previous_tag(self, repo, tag, all_tags):
        """
        Find the previous tag to the given tag.
        First tries to find semantically similar tag from the same version family,
        then falls back to chronologically previous tag if semantic match is not found.
        """
        tag_date = tag['date']
        tag_name = tag['name']

        # Simple default values for fallback
        fallback = {
            'name': 'initial',
            'commit': tag['commit'],
            'date': tag_date - datetime.timedelta(days=1),
            'message': 'Initial state',
            'url': tag['url']
        }

        try:
            # Sort tags by date (newest first)
            sorted_tags = sorted(all_tags, key=lambda t: t['date'], reverse=True)
            
            # Try to find semantically similar tag first (from same version family)
            same_family_tags = []
            
            # Check if the tag looks like semantic versioning (vX.Y.Z or X.Y.Z)
            version_match = re.match(r'(v?\d+\.\d+)', tag_name)
            if version_match:
                # Get the family prefix (e.g., v1.2 or 1.2)
                version_family = version_match.group(1)
                logger.info(f"Looking for previous tag in version family {version_family} for tag {tag_name}")
                
                # Find all tags from the same family
                for t in sorted_tags:
                    if t['name'] != tag_name and t['date'] < tag_date and t['name'].startswith(version_family):
                        same_family_tags.append(t)
                
                # Return the most recent tag from the same family
                if same_family_tags:
                    logger.info(f"Found semantic previous tag from same family: {same_family_tags[0]['name']} for tag {tag_name}")
                    return same_family_tags[0]
            
            # If no semantic match found, fall back to chronological order
            logger.info(f"No semantic previous tag found for {tag_name}, falling back to chronological order")
            
            for t in sorted_tags:
                if t['date'] < tag_date and t['name'] != tag_name:
                    logger.info(f"Found chronological previous tag: {t['name']} for tag {tag_name}")
                    return t

            # If no previous tag found, try to find the first commit
            try:
                commits = list(repo.get_commits(sha=repo.default_branch).reversed)
                if commits:
                    initial_commit = commits[0]
                    logger.info(f"No previous tag found for {tag_name}, using initial commit")
                    return {
                        'name': 'initial',
                        'commit': initial_commit.sha,
                        'date': fix_timezone(initial_commit.commit.author.date),
                        'message': initial_commit.commit.message,
                        'url': initial_commit.html_url
                    }
            except Exception as e:
                logger.warning(f"Error finding initial commit: {e}")
                # Continue to fallback
            
            # Return fallback if no tag or commit was found
            logger.info(f"No previous tag or initial commit found for {tag_name}, using fallback")
            return fallback

        except Exception as e:
            logger.error(f"Error finding previous tag for {tag_name}: {e}")
            return fallback

    def collect_component_jobs(self) -> list[dict[str, Any]]:
        """
        Collect all valid components to process.
        Returns a list of component jobs with basic information.
        Note: Tag fetching is done in process_component_job for better parallelization.
        """
        logger.info("Collecting components to process...")
        components_details = load_component_details()
        repos = get_repositories(self.github, self.organization)
        component_jobs = []

        for repo in repos:
            #if repo.name !="component-delta-lake":
            #    continue
            component_names = get_component_name(repo)
            logger.info(f"Found component names for {repo.name}: {component_names}")

            # Track valid components count for this repo
            valid_components_count = 0

            # Check each component and add valid ones directly to component_jobs
            for component_name in component_names:
                matched_component = next((c for c in components_details if c.get('id') == component_name), None)
                if matched_component:
                    component_stage = determine_component_stage(matched_component)
                    logger.info(f"Component {component_name} is in {component_stage} stage")

                    # Add directly to component_jobs
                    component_jobs.append({
                        'repo': repo,
                        'component_name': component_name,
                        'component_details': matched_component,
                        'component_stage': component_stage
                    })

                    valid_components_count += 1
                else:
                    logger.info(f"No details found for component {component_name}, skipping")

            # Log if no valid components found for this repository
            if valid_components_count == 0:
                logger.info(f"No valid components found for repository {repo.name}, skipping")

        logger.info(f"Collected {len(component_jobs)} component jobs to process")
        return component_jobs

    def process_component_job(self, job: dict[str, Any]) -> list[dict[str, Any]]:
        """
        Process a single component job.
        This includes fetching tags (which is now done here in parallel) and processing them.
        Returns a list of entries (release notes) created for this component.
        """
        repo = job['repo']
        component_name = job['component_name']
        component_details = job['component_details']
        component_stage = job['component_stage']

        logger.info(f"Starting processing for component {component_name} in repo {repo.name}")
        entries = []

        # Fetch tags here (in parallel) - this is the most time-consuming part
        tags = get_tags_in_period(repo, self.start_date, self.end_date)

        # Skip if no tags in period
        if not tags:
            logger.info(f"No tags found for {repo.name} in the specified period, skipping component {component_name}")
            return entries

        # Get all tags for this repo (for finding previous tags)
        all_tags = get_repo_tags(repo)

        # Normalize component name for filename
        component_name_normalized = component_name.replace('.', '-').replace(' ', '-').lower()

        # Process each tag directly, checking if it's already been processed
        processed_tags_count = 0
        for tag in tags:
            # Check if we've already processed this release
            timestamp = tag['date'].strftime('%Y-%m-%d-%H-%M-%S')
            file_name = f"{timestamp}_{component_stage.lower()}_{tag['name']}_{component_name_normalized}.md"
            file_path = os.path.join("release_notes", file_name)

            # Skip if file already exists
            if os.path.exists(file_path):
                continue

            processed_tags_count += 1

            try:
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

                # Save individual release note
                is_new = save_component_release_note(entry)

                if is_new:
                    entries.append(entry)
                    logger.info(f"Created release note for {component_name} {tag['name']}")

            except Exception as e:
                logger.error(f"Error processing tag {tag['name']} for component {component_name}: {e}")

        if processed_tags_count > 0:
            logger.info(f"Processed {processed_tags_count} new tags for component {component_name}")
        else:
            logger.info(f"No new tags to process for component {component_name}")

        return entries

    def generate_timeline(self):
        """Generate a timeline of all changes across repositories using parallel processing."""
        logger.info("Generating timeline of changes with parallel processing")

        # Step 1: Collect all component jobs (without fetching tags)
        component_jobs = self.collect_component_jobs()

        # Step 2: Process component jobs in parallel (including tag fetching)
        # Use ThreadPoolExecutor for parallel processing with max 3 workers
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            # Submit all jobs to the executor
            future_to_job = {
                executor.submit(self.process_component_job, job): job
                for job in component_jobs
            }

            # Process results as they complete
            for future in concurrent.futures.as_completed(future_to_job):
                job = future_to_job[future]
                try:
                    # Get the entries from this job
                    job_entries = future.result()

                    logger.info(f"Completed processing component {job['component_name']} - "
                                f"generated {len(job_entries)} entries")

                except Exception as e:
                    logger.error(f"Error processing component {job['component_name']}: {e}")
