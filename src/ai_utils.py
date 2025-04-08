#!/usr/bin/env python3
import logging

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
    """Generate AI description for release notes."""
    try:
        # Format the changes as a readable list
        changes_list = "\n".join([f"- {change}" for change in changes])
        
        # Create GitHub comparison URL
        github_compare_url = f"https://github.com/keboola/{repo_name}/compare/{previous_tag}...{current_tag}"

        # Phase 1: Analyze changes
        analysis_prompt = f"""
        Analyze code changes in {github_compare_url}. Focus ONLY on changes that affect data processing.

        CRITICAL: Only include changes that:
        - Change how data is processed
        - Change what data is output
        - Change how errors are handled
        - Add/remove configuration options
        - Change component behavior

        IGNORE:
        - CI/CD, docs, tests, builds
        - Internal scripts
        - Developer portal
        - Commit authors and timestamps

        Available info:
        - Changes: {changes_list}
        - Compare URL: {github_compare_url}

        Output format:
        1. DATA CHANGES:
           - What changed
           - File and location
           - Impact on data
           Example: "Removed column swap - data order unchanged"

        2. OTHER CHANGES:
           - What changed
           - File
           - Impact

        Be factual. Only include verified changes. Do not include commit authors or timestamps.
        """

        # Get analysis from GPT-4
        analysis_response = openai_client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a data change analyzer. Your job is to identify changes that affect data processing. Ignore internal changes and commit metadata. Be precise and factual."},
                {"role": "user", "content": analysis_prompt}
            ],
            max_tokens=500,
            temperature=0.3
        )
        
        analysis = analysis_response.choices[0].message.content

        # Phase 2: Generate release notes
        writing_prompt = f"""
        Write release notes based on this analysis:
        {analysis}

        Format:
        Title: [Most important data change]
        
        Excerpt: [One line about data impact]
        
        Post detail: [Just the facts about data changes]

        Rules:
        - Be brief and factual
        - Match length to significance of changes
        - No marketing language
        - No internal changes
        - No assumptions
        - Do not include commit authors or timestamps
        """

        # Generate release notes with GPT-4
        response = openai_client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a technical writer. Write brief, factual release notes. Match length to significance. No marketing language. Do not include commit metadata."},
                {"role": "user", "content": writing_prompt}
            ],
            max_tokens=500,
            temperature=0.5
        )

        return response.choices[0].message.content

    except Exception as e:
        print(f"Error generating AI description: {str(e)}")
        return None
