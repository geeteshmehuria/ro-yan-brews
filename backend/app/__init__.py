"""Load .env before any submodule reads os.getenv(). Real environment variables
(e.g. Render dashboard vars in production) still win — load_dotenv doesn't override
them — so this only fills in values when they aren't already set."""
from dotenv import load_dotenv

load_dotenv()
