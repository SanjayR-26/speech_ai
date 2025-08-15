import sys
import os

# Add the fastapi_app directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
fastapi_dir = os.path.join(current_dir, 'fastapi_app')
sys.path.insert(0, fastapi_dir)

# Now import the FastAPI app from the package module
from fastapi_app.main import app
