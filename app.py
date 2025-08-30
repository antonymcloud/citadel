"""Main application module for Citadel."""
from citadel import create_app
import os

# Set environment variables for development
os.environ['MOCK_BORG'] = 'false'

# Mount management configuration
os.environ['CITADEL_MOUNT_BASE_DIR'] = '/tmp/citadel/mounts'
os.environ['CITADEL_ENABLE_MOUNT_CLEANUP'] = 'true'
os.environ['CITADEL_MOUNT_CLEANUP_INTERVAL_HOURS'] = '12'
os.environ['CITADEL_MOUNT_MAX_AGE_HOURS'] = '24'
os.environ['CITADEL_AUTO_UNMOUNT_ORPHANED'] = 'true'

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get('PORT', 5000)), debug=True)
