import argparse
from pathlib import Path

from dotenv import load_dotenv

# Parse command-line arguments
parser = argparse.ArgumentParser(description="Run the FastAPI application.")
parser.add_argument("--production", action="store_true", help="Run in production mode without loading .env file")
args = parser.parse_args()

# Get the root directory (where .env file is located)
root_dir = Path(__file__).parent.parent.parent
env_path = root_dir / ".env"

# Load environment variables from .env file if not in production mode
if not args.production:
    if env_path.exists():
        load_dotenv(env_path)
        print(f"Loaded environment from {env_path}")
    else:
        print(f"Warning: .env file not found at {env_path}")
else:
    print("Running in production mode, not loading .env file")

# Import and run the FastAPI application
if __name__ == "__main__":
    import uvicorn
    from utils.configuration import config

    print(f"Running with configuration: {config}")
    uvicorn.run("app:app", host="0.0.0.0", port=config.api_port, reload=config.isDev)
