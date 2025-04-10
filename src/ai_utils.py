#!/usr/bin/env python3
import google.generativeai as genai
from src.config import logger, GOOGLE_AI_MODEL, GOOGLE_AI_API_KEY


def initialize_google_ai_client():
    """Initialize Google AI client if API key is available."""
    if not GOOGLE_AI_API_KEY:
        logger.info("Google AI API key not provided - AI summaries disabled")
        return None

    try:
        # Configure the API key
        genai.configure(api_key=GOOGLE_AI_API_KEY)

        # Create a model instance
        model = genai.GenerativeModel(GOOGLE_AI_MODEL)
        logger.info("Google AI client initialized - will try to generate AI summaries")
        return model

    except Exception as e:
        logger.error(f"Error initializing Google AI client: {e}")
        logger.info("AI summaries disabled due to client initialization error")
        return None


def generate_ai_description(google_ai_model, repo_name, previous_tag, current_tag, changes):
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
        - Change how main python code works

        IGNORE:
        - CI/CD, docs, tests, builds
        - Internal scripts
        - Developer portal
        - Commit authors and timestamps

        Available info:
        - Changes: {changes_list}
        - Compare URL: {github_compare_url}

        Output format:
        1. MAIN FUNCTIONAL CHANGES:
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

        # Get analysis from Gemini
        analysis_response = google_ai_model.generate_content(analysis_prompt)
        analysis = analysis_response.text

        # Phase 2: Generate release notes
        writing_prompt = f"""
        Changelog posts announce new features and functionalities in our (Keboola) platform.
        Write concise "changelog" posts based on these changes:
        {analysis}
        
        Rules:
        - Start directly with the content
        - Do not include any introductory or closing comments
        - Do not include markdown formatting instructions
        - Do not use code blocks or markdown formatting
        - Be concise and strictly factual
        - Describe only the changes provided in the analysis
        - Do not speculate or invent usage examples
        - Stick only to the confirmed changes and their direct impact
        
        The post should contain following sections:
        - Title (this is also displayed in in platform notifications)
          - It should be short, poignant and concise. Ideally attracting attention for click.
        - Excerpt - a short sentence that describes what is the feature about.
          - It should be short and capture the main announcement of the feature.
          - It is also displayed in the detail of the post, so it should not duplicate with the initial sentence in the detail. Rather, it should summarise the post detail
        - Post detail
          - These are couple of paragraphs describing what the feature is about.
          - It should not be too chatty, but capture the main features and pointing out the value.
          - It should be catchy, but not overly informal.
        """

        # Generate release notes with Gemini
        response = google_ai_model.generate_content(writing_prompt)
        return response.text

    except Exception as e:
        raise e
