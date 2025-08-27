"""Main application module for Tower of Borg."""
from towerofborg import create_app
import os

# Set environment variables for development
os.environ['MOCK_BORG'] = 'false'

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get('PORT', 5000)), debug=True)
