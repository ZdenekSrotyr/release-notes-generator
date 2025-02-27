#!/usr/bin/env python3
import os
import glob
import datetime
from jinja2 import Environment, FileSystemLoader
from src.config import logger, TEMPLATE_DIR, RELEASE_NOTES_DIR

def detect_time_period_from_last_run(days=30):
    """Detect time period by finding the latest release notes file.
    If no files exist, use last N days specified by the days parameter.
    """
    # Get the list of all release notes files
    files = glob.glob(f"{RELEASE_NOTES_DIR}/*.md")

    today = datetime.datetime.now()
    if not files:
        # If no previous files, use last N days
        start_date = (today - datetime.timedelta(days=days))
        logger.info(f"No previous release notes found, using last {days} days")
        return start_date, today

    # Get the latest file by timestamp in filename
    # The timestamp is the first part of the filename before the first underscore
    latest_file = max(files, key=lambda f: os.path.basename(f).split('_')[0])
    filename = os.path.basename(latest_file)

    # Extract the timestamp from the filename (YYYY-MM-DD-HH-MM-SS_stage_tag_component-name.md)
    timestamp_str = filename.split('_')[0]

    # Parse the timestamp
    latest_date = datetime.datetime.strptime(timestamp_str, '%Y-%m-%d-%H-%M-%S')

    # If the latest date is today, we still want to include today
    logger.info(f"Using time period: {latest_date.strftime('%Y-%m-%d')}-to-{today.strftime('%Y-%m-%d')}")

    return latest_date, today

def save_component_release_note(entry):
    """Save a release note for a single component release."""
    # Skip creation of release notes if there are no changes between tags
    if not entry['changes']:
        logger.info(
            f"No changes found between {entry['previous_tag']} and {entry['tag_name']} for {entry['component_name']}, skipping release note")
        return False

    # Format: YYYY-MM-DD-HH-MM-SS_stage_tag_component-name.md
    timestamp = entry['date'].strftime('%Y-%m-%d-%H-%M-%S')
    component_name = entry['component_name'].replace('.', '-').replace(' ', '-').lower()
    tag_name = entry['tag_name']
    # Convert stage to lowercase for filename
    stage = entry['component_stage'].lower()
    file_name = f"{timestamp}_{stage}_{tag_name}_{component_name}.md"
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

    # Create directory if it doesn't exist
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    # Write the file
    with open(file_path, 'w') as f:
        f.write(content)

    logger.info(f"Created release note: {file_path}")
    return True 