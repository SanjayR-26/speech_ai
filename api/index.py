import sys
import os

# Add the fastapi_app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'fastapi_app'))

# Now import the FastAPI app
from main import app

# For Vercel, we need to export the app directly
# Vercel's @vercel/python runtime handles FastAPI apps natively
