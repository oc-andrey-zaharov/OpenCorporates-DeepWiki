import logging
import os
import sys

from dotenv import load_dotenv

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# Check if we're in development mode (before loading .env)
# Check common environment variable names: ENVIRONMENT, ENV, NODE_ENV
env_value = (
    os.environ.get("ENVIRONMENT") or os.environ.get("ENV") or os.environ.get("NODE_ENV")
)
is_development = env_value != "production"

# Load environment variables from .env file
# In development, .env values override environment variables
# In production, environment variables take precedence (deployment-provided)
load_dotenv(override=is_development)

from api.logging_config import setup_logging

# Configure logging
setup_logging()
logger = logging.getLogger(__name__)

# Configure watchfiles logger to show file paths
watchfiles_logger = logging.getLogger("watchfiles.main")
watchfiles_logger.setLevel(logging.DEBUG)  # Enable DEBUG to see file paths

import uvicorn

# Check for required environment variables
required_env_vars = ["GOOGLE_API_KEY", "OPENAI_API_KEY"]
missing_vars = [var for var in required_env_vars if not os.environ.get(var)]
if missing_vars:
    logger.warning(f"Missing environment variables: {', '.join(missing_vars)}")
    logger.warning("Some functionality may not work correctly without these variables.")

# Configure Google Generative AI
import google.generativeai as genai

from api.config import GOOGLE_API_KEY

if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)
else:
    logger.warning("GOOGLE_API_KEY not configured")


def main():
    # Get port from environment variable or use default
    port = int(os.environ.get("PORT", 8001))

    # Import the app here to ensure environment variables are set first

    logger.info(f"Starting DeepWiki API on port {port}")

    # Run the FastAPI app with uvicorn
    uvicorn.run(
        "api.server.server:app",
        host="0.0.0.0",
        port=port,
        reload=is_development,
        reload_dirs=["./api"] if is_development else None,
        reload_excludes=["**/logs/*", "**/__pycache__/*", "**/*.pyc"]
        if is_development
        else None,
    )


if __name__ == "__main__":
    main()
