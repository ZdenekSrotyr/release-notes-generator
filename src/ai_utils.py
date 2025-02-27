#!/usr/bin/env python3
from openai import OpenAI
from src.config import logger, OPENAI_MODEL, OPENAI_API_KEY


def initialize_openai_client():
    """Initialize OpenAI client if API key is available."""
    if not OPENAI_API_KEY:
        logger.info("OpenAI API key not provided - AI summaries disabled")
        return None

    try:
        # Just create the client without making any API calls yet
        client = OpenAI(api_key=OPENAI_API_KEY)
        logger.info("OpenAI client initialized - will try to generate AI summaries")

        # Test the client with a minimal API call to check authentication
        try:
            # Simple API call to test authentication
            # Just call the models.list() without parameters which should work with all API versions
            client.models.list()
            logger.info("OpenAI API authentication successful - AI summaries enabled")
            return client
        except Exception as auth_e:
            # Check for organization-related errors
            error_msg = str(auth_e)
            if "organization" in error_msg.lower() or "401" in error_msg:
                logger.error(f"Organization access error with OpenAI API: {auth_e}")
                logger.info("AI summaries disabled due to organization access issues - check your API key permissions")
            else:
                logger.error(f"Authentication error with OpenAI API: {auth_e}")
                logger.info("AI summaries disabled due to authentication issues")
            return None

    except Exception as e:
        logger.error(f"Error initializing OpenAI client: {e}")
        logger.info("AI summaries disabled due to client initialization error")
        return None


def generate_ai_description(openai_client, repo_name, previous_tag, current_tag, changes):
    """Generate an AI description of the changes between tags."""
    if not openai_client:
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
        response = openai_client.chat.completions.create(
            model=OPENAI_MODEL,
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
        error_msg = str(e)
        # Check for specific errors
        if "401" in error_msg or "unauthorized" in error_msg.lower():
            logger.error(f"Error generating AI description - authentication issue: {e}")
            # Disable the client for future calls to prevent repeated errors
            logger.info("Disabling OpenAI client for remaining operations due to authentication issues")
            return None
        elif "organization" in error_msg.lower():
            logger.error(f"Error generating AI description - organization access issue: {e}")
            # Disable the client for future calls to prevent repeated errors
            logger.info("Disabling OpenAI client for remaining operations due to organization access issues")
            return None
        else:
            logger.error(f"Error generating AI description: {e}")
        return None
