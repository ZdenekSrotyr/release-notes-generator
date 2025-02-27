#!/usr/bin/env python3
import yaml
import re
import requests
from src.config import logger, KEBOOLA_STORAGE_API_URL

def get_component_name(repo):
    """Extract component names from workflow files.
    Returns a list of component names found in .github/*.yml files.
    """
    component_names = set()  # Use set to avoid duplicates
    
    try:
        # Recursively find all .yml files
        workflow_files = find_yml_files_in_directory(repo, ".github")
        
        # Process each yml file
        for workflow_file in workflow_files:
            try:
                component_names.update(extract_component_names_from_file(workflow_file))
            except Exception as e:
                logger.warning(f"Error processing workflow file {workflow_file.path}: {e}")
    
    except Exception as e:
        logger.warning(f"Error accessing .github directory in {repo.name}: {e}")
    
    # If no component names found, use repo name
    if not component_names:
        return [repo.name]
        
    return list(component_names)

def find_yml_files_in_directory(repo, directory_path):
    """Recursively find all .yml files in a directory."""
    yml_files = []
    try:
        contents = repo.get_contents(directory_path)
        for content in contents:
            if content.type == "dir":
                try:
                    yml_files.extend(find_yml_files_in_directory(repo, content.path))
                except Exception as e:
                    logger.warning(f"Error accessing directory {content.path}: {e}")
            elif content.type == "file" and content.path.endswith(('.yml', '.yaml')):
                yml_files.append(content)
    except Exception as e:
        logger.warning(f"Error accessing directory {directory_path}: {e}")
    return yml_files

def extract_component_names_from_file(workflow_file):
    """Extract component names from a workflow file."""
    component_names = set()
    try:
        workflow_content = workflow_file.decoded_content.decode('utf-8')
        
        # Skip if file doesn't contain the key we're looking for
        if 'KBC_DEVELOPERPORTAL_APP' not in workflow_content:
            return component_names
            
        # Try parsing YAML first
        try:
            workflow_yaml = yaml.safe_load(workflow_content)
            if isinstance(workflow_yaml, dict):
                # Check different levels of the YAML structure
                component_names.update(check_env_section(workflow_yaml.get('env')))
                component_names.update(check_jobs_section(workflow_yaml.get('jobs', {})))
        except Exception as e:
            logger.warning(f"Error parsing YAML in {workflow_file.path}: {e}")
            
        # Try regex approach as backup or additional check
        component_names.update(extract_component_names_with_regex(workflow_content))
            
    except Exception as e:
        logger.warning(f"Error reading workflow file content: {e}")
        
    return component_names

def check_env_section(env_section):
    """Check env section for component names."""
    component_names = set()
    if isinstance(env_section, dict):
        app_name = env_section.get('KBC_DEVELOPERPORTAL_APP')
        if app_name:
            component_names.add(app_name)
    return component_names

def check_jobs_section(jobs_section):
    """Check jobs section for component names."""
    component_names = set()
    if not isinstance(jobs_section, dict):
        return component_names
        
    for job_name, job in jobs_section.items():
        if not isinstance(job, dict):
            continue
            
        # Check job-level env
        component_names.update(check_env_section(job.get('env')))
        
        # Check steps
        if 'steps' in job and isinstance(job['steps'], list):
            for step in job['steps']:
                if isinstance(step, dict):
                    component_names.update(check_env_section(step.get('env')))
                    
    return component_names

def extract_component_names_with_regex(content):
    """Extract component names using regex patterns."""
    component_names = set()
    # Match patterns like: KBC_DEVELOPERPORTAL_APP: value or KBC_DEVELOPERPORTAL_APP=value
    patterns = [
        r'KBC_DEVELOPERPORTAL_APP: *([^\s]+)',  # YAML style
        r'KBC_DEVELOPERPORTAL_APP *= *([^\s]+)'  # ENV style
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, content)
        for match in matches:
            # Clean up the match (remove quotes, etc)
            clean_match = match.strip('\'"')
            if clean_match:
                component_names.add(clean_match)
                
    return component_names

def load_component_details():
    """Get component details from Keboola Connection Storage API."""
    try:
        # Use the Storage API to get all components
        api_url = KEBOOLA_STORAGE_API_URL

        # Make API request without authentication
        response = requests.get(api_url)

        # Check if the request was successful
        if response.status_code == 200:
            # Parse JSON response
            return response.json().get('components')

        else:
            logger.warning(f"Failed to retrieve components list: HTTP {response.status_code}")
            logger.debug(f"Response content: {response.text}")

    except Exception as e:
        logger.error(f"Error retrieving component details: {e}")
        
    # Return empty list if failed
    return []

def determine_component_stage(component_details):
    """Determine the stage of a component based on its flags."""
    if not component_details or 'flags' not in component_details:
        return "GA"  # Default if no flags information
        
    flags = component_details.get('flags', [])
    
    if "appInfo.experimental" in flags:
        return "Experimental"
    elif "appInfo.beta" in flags:
        return "Beta"
    else:
        return "GA" 