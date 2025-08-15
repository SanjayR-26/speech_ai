import sys
import os
from mangum import Mangum

# Add the fastapi_app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'fastapi_app'))

# Now import the FastAPI app
from main import app

# Wrap the FastAPI app with Mangum for serverless deployment
handler = Mangum(app)
