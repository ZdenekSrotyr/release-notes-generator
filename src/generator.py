#!/usr/bin/env python3
import os
import datetime
import concurrent.futures
from typing import Any, List
import re

from src.config import logger
from src.github_graphql_utils import get_repositories_with_full_data, get_all_repositories_data_in_single_request, get_tags_in_period, get_changes_between_tags, get_repo_tags
from src.component_utils import get_component_name, load_component_details, determine_component_stage
from src.keboola_utils import detect_time_period_from_state, update_state_file, save_release_to_table
from src.config import load_configuration, validate_configuration
from src.ai_utils import initialize_google_ai_client, generate_ai_description
from keboola.component import CommonInterface


class ReleaseNotesGenerator:
    """Main class for generating release notes."""

    def __init__(self, github_token: str, ci: CommonInterface):
        """Initialize generator with GitHub token and Keboola interface."""
        # Always use the best available method (ultra-optimized GraphQL)
        from src.github_graphql_utils import initialize_github_client as initialize_graphql_client
        self.github = initialize_graphql_client(github_token)
        
        # Initialize Keboola interface
        self.ci = ci
        self.organization = "keboola"
        
        # Load configuration
        self.config = load_configuration(ci)
        
        # Initialize Google AI client if available
        self.google_ai_model = initialize_google_ai_client(self.config.google_ai_api_key)
        
        # Detect time period from state file
        self.start_date, self.end_date = detect_time_period_from_state(ci, days=self.config.days_back)
        
        # Ensure dates have timezone information for GraphQL compatibility
        from src.github_graphql_utils import fix_timezone
        self.start_date = fix_timezone(self.start_date)
        self.end_date = fix_timezone(self.end_date)
        
        logger.info(
            f"Using date range: {self.start_date.strftime('%Y-%m-%d')} to {self.end_date.strftime('%Y-%m-%d')}")
        
        # Initialize tracking for new releases
        self.new_releases = []

    def get_repositories_optimized(self):
        """Get repositories using the most optimized method (ultra-optimized single GraphQL request)."""
        logger.info("Using ultra-optimized single GraphQL request for all repositories")
        from src.github_graphql_utils import get_all_repositories_data_in_single_request
        return get_all_repositories_data_in_single_request(self.github, self.organization)

    @staticmethod
    def find_previous_tag(repo, tag, all_tags, organization):
        """
        Find the previous tag for a given tag.
        Returns a tag object with name, commit, date, message, and url.
        """
        tag_name = tag['name']
        tag_date = tag['date']

        # Create fallback tag
        fallback = {
            'name': 'initial',
            'commit': tag['commit'],
            'date': tag_date - datetime.timedelta(days=1),
            'message': 'Initial state',
            'url': f"https://github.com/{organization}/{repo.name}/commit/{tag['commit']}"
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
                    logger.info(
                        f"Found semantic previous tag from same family: {same_family_tags[0]['name']} for tag {tag_name}")
                    return same_family_tags[0]

            # If no semantic match found, fall back to chronological order
            logger.info(f"No semantic previous tag found for {tag_name}, falling back to chronological order")

            for t in sorted_tags:
                if t['date'] < tag_date and t['name'] != tag_name:
                    logger.info(f"Found chronological previous tag: {t['name']} for tag {tag_name}")
                    return t

            # If no previous tag found, use fallback
            logger.info(f"No previous tag found for {tag_name}, using fallback")
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
        repos = self.get_repositories_optimized()
        component_jobs = []

        for repo in repos:
            # Use pre-fetched component data if available, otherwise fetch it
            if hasattr(repo, '_workflow_files'):
                logger.info(f"Using pre-fetched component data for {repo.name}")
                # Use the GraphQL version of get_component_name that works with pre-fetched data
                from src.github_graphql_utils import get_component_name as get_component_name_graphql
                component_names = get_component_name_graphql(repo, repo._github_client_data)
            else:
                logger.info(f"Fetching component data for {repo.name}")
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
        
        # Debug: Log all component jobs to see if there are duplicates
        for i, job in enumerate(component_jobs):
            logger.info(f"Job {i+1}: {job['component_name']} in repo {job['repo'].name}")
        
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

        # Use pre-fetched tags if available, otherwise fetch them
        if hasattr(repo, '_tags') and repo._tags:
            logger.info(f"Using pre-fetched tags for {repo.name}")
            all_tags = repo._tags
            # Filter tags by date period
            tags = []
            for tag in all_tags:
                if self.start_date <= tag['date'] <= self.end_date:
                    tags.append(tag)
        else:
            logger.info(f"Fetching tags for {repo.name}")
            # Fetch tags here (in parallel) - this is the most time-consuming part
            tags = get_tags_in_period(repo, self.start_date, self.end_date)
            # Get all tags for this repo (for finding previous tags)
            all_tags = get_repo_tags(repo)

        # Skip if no tags in period
        if not tags:
            logger.info(f"No tags found for {repo.name} in the specified period, skipping component {component_name}")
            return entries

        # Process each tag
        processed_tags_count = 0
        for tag in tags:
            processed_tags_count += 1

            try:
                # Find the previous tag
                previous_tag = self.find_previous_tag(repo, tag, all_tags, self.organization)

                # Get changes between tags
                change_data = get_changes_between_tags(repo, previous_tag, tag)
                logger.info(f"Got {len(change_data.get('changes', []))} changes between {previous_tag['name']} and {tag['name']} for {repo.name}")

                # Generate AI description if enabled
                ai_description = None
                if self.google_ai_model and change_data['changes']:
                    ai_description = generate_ai_description(
                        self.google_ai_model,
                        repo.name,
                        previous_tag['name'],
                        tag['name'],
                        change_data['changes']
                    )
                    # If ai_description failed and returned None, disable the model for future tags
                    if ai_description is None and self.google_ai_model is not None:
                        logger.info("AI description generation failed - disabling for subsequent tags")
                        self.google_ai_model = None

                # Add the AI description to the change data
                change_data['ai_description'] = ai_description

                # Create entry for this release
                entry = {
                    'date': tag['date'],
                    'type': 'release',
                    'repo_name': repo.name,
                    'github_organization': self.organization,
                    'component_name': component_name,
                    'component_details': component_details,
                    'tag_name': tag['name'],
                    'changes': change_data['changes'],
                    'tag_url': f"https://github.com/{self.organization}/{repo.name}/releases/tag/{tag['name']}",
                    'ai_description': change_data['ai_description'],
                    'previous_tag': previous_tag['name'],
                    'component_stage': component_stage
                }

                # Save to table
                logger.info(f"Attempting to save release for {component_name} {tag['name']} (component_id: {component_name})")
                is_new = save_release_to_table(self.ci, entry, self.config.table_name)

                if is_new:
                    entries.append(entry)
                    logger.info(f"Created release note for {component_name} {tag['name']}")
                else:
                    logger.info(f"Release note for {component_name} {tag['name']} already exists, skipping")

            except Exception as e:
                logger.error(f"Error processing tag {tag['name']} for component {component_name}: {e}")

        if processed_tags_count > 0:
            logger.info(f"Processed {processed_tags_count} tags for component {component_name}")
        else:
            logger.info(f"No tags to process for component {component_name}")

        return entries

    def generate_timeline(self) -> List[dict[str, Any]]:
        """Generate a timeline of all changes across repositories using parallel processing."""
        logger.info("Generating timeline of changes with sequential processing for debugging")

        # Step 1: Collect all component jobs (without fetching tags)
        component_jobs = self.collect_component_jobs()

        # Step 2: Process component jobs sequentially for debugging
        logger.info(f"Processing {len(component_jobs)} component jobs sequentially")
        
        for i, job in enumerate(component_jobs):
            try:
                logger.info(f"Processing job {i+1}/{len(component_jobs)}: {job['component_name']}")
                
                # Get the entries from this job
                job_entries = self.process_component_job(job)

                # Add to new releases list
                self.new_releases.extend(job_entries)

                logger.info(f"Completed processing component {job['component_name']} - "
                            f"generated {len(job_entries)} entries")
                
                # Force log flush
                import sys
                sys.stdout.flush()

            except Exception as e:
                logger.error(f"Error processing component {job['component_name']}: {e}")
                # Force log flush
                import sys
                sys.stdout.flush()

        # Update state file with latest processed date if we have new releases
        if self.new_releases:
            latest_date = max(release['date'] for release in self.new_releases)
            update_state_file(self.ci, latest_date)

        logger.info(f"Generated {len(self.new_releases)} new release notes")
        return self.new_releases
