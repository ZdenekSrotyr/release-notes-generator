#!/usr/bin/env python3
import yaml
import re
import requests
from src.config import logger, KEBOOLA_STORAGE_API_URL


def get_component_name(repo):
    """Extract component names from workflow files.
    Returns a list of component names found in .github/*.yml files.
    Looks for various identifiers:
    - KBC_DEVELOPERPORTAL_APP/app (case insensitive)
    - KBC_DEVELOPERPORTAL_ID  (case insensitive)
    - APP_NAME  (case insensitive)
    - KBC_DEVELOPERPORTAL_VENDOR (case insensitive) - used as prefix if component doesn't have a dot
    
    Values starting with "${{" (GitHub Actions variables) are ignored.
    Only values on the same line as the key are captured.
    """
    component_names = set()  # Use set to avoid duplicates
    vendors = set()  # Track vendors separately

    try:
        # Get all yml files in .github directory and its subdirectories
        yml_files = find_yml_files_in_directory(repo, ".github")
        
        # Process each yml file
        for yml_file in yml_files:
            try:
                file_content = yml_file.decoded_content.decode('utf-8')
                
                # Split content into lines to ensure we only match values on the same line
                lines = file_content.split('\n')
                
                for line in lines:
                    # Process only non-empty lines
                    if not line.strip():
                        continue
                        
                    # Find component identifiers - ensure values are on the same line
                    # Match patterns like: KEY: value, KEY: "value", KEY: 'value'
                    app_match = re.search(r'(?i)KBC_DEVELOPERPORTAL_APP\s*:\s*[\'"]?([a-zA-Z0-9._-]+)[\'"]?', line)
                    id_match = re.search(r'(?i)KBC_DEVELOPERPORTAL_ID\s*:\s*[\'"]?([a-zA-Z0-9._-]+)[\'"]?', line)
                    app_name_match = re.search(r'(?i)APP_NAME\s*:\s*[\'"]?([a-zA-Z0-9._-]+)[\'"]?', line)
                    vendor_match = re.search(r'(?i)KBC_DEVELOPERPORTAL_VENDOR\s*:\s*[\'"]?([a-zA-Z0-9._-]+)[\'"]?', line)
                    
                    # Add component matches
                    for match in [app_match, id_match, app_name_match]:
                        if match and match.group(1) and not match.group(1).startswith('${{'):
                            component_names.add(match.group(1))
                    
                    # Add vendor match
                    if vendor_match and vendor_match.group(1) and not vendor_match.group(1).startswith('${{'):
                        vendors.add(vendor_match.group(1))
                
            except Exception as e:
                logger.warning(f"Error processing file {yml_file.path}: {e}")
    except Exception as e:
        logger.warning(f"Error accessing .github directory in {repo.name}: {e}")

    # If no component names found, use repo name
    if not component_names:
        component_names.add(repo.name)
    
    # Process vendor prefixes for components without dots
    final_component_names = set()
    for component_name in component_names:
        if '.' not in component_name:
            # For components without dots, try to prefix with vendor
            for vendor in vendors:
                vendor_prefixed = f"{vendor}.{component_name}"
                final_component_names.add(vendor_prefixed)
            
            # Also keep the original if no vendors or multiple vendors
            if not vendors or len(vendors) > 1:
                final_component_names.add(component_name)
        else:
            # Components with dots are kept as-is
            final_component_names.add(component_name)
    
    return list(final_component_names)


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


def check_env_section(env_section):
    """Check env section for component names."""
    component_names = set()
    if isinstance(env_section, dict):
        app_name = env_section.get('KBC_DEVELOPERPORTAL_APP')
        if app_name:
            component_names.add(app_name)
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
        return "EXPERIMENTAL"
    elif "appInfo.beta" in flags:
        return "BETA"
    elif "excludeFromNewList" in flags:
        return "HIDDEN"
    else:
        return "GA"
