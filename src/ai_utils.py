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
        
        Keep it under 150 words.
        Provide a concise technical summary focusing on the most significant program logic changes.
        Ignore Added or deleted files!
         
        The post should contain following sections:

        Title (this is also displayed in in platform notifications)
        It should be short, poignant and concise. Ideally attracting attention for click.
        Excerpt - a short sentence that describes what is the feature about.
        It should be short and capture the main announcement of the feature.
        It is also displayed in the detail of the post, so it should not duplicate with the initial sentence in the detail. Rather, it should summarise the post detail
        Post detail
        These are couple of paragraphs describing what the feature is about.
        It should not be too chatty, but capture the main features and pointing out the value.
        It should be catchy, but not overly informal.
        """

        # Make the API call
        response = openai_client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": "You are a technical writer summarizing software changes. "
                                              "You are tasked with writing concise 'changelog' posts. "
                                              "Changelog posts announce new features and functionalities in our (Keboola) platform."},
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
