# Mount Management

Citadel provides tools for managing Borg archive mounts, including:

1. **Mount Archive Viewing**: Browse files in a mounted archive directly through the web interface
2. **Multi-select and Batch Downloads**: Select multiple files/folders for downloading as a single ZIP
3. **Automatic Orphaned Mount Cleanup**: Scheduled tasks to unmount archives left mounted for too long
4. **Admin Interface**: For manually managing mounts and force unmounting stuck archives
5. **CLI Commands**: Command-line tools for managing mounts

## Mount Management Configuration

You can configure mount management through environment variables:

```
# Base directory for all archive mounts
CITADEL_MOUNT_BASE_DIR=/tmp/citadel/mounts

# Enable/disable automatic orphaned mount cleanup
CITADEL_ENABLE_MOUNT_CLEANUP=true

# How often to run the cleanup (in hours)
CITADEL_MOUNT_CLEANUP_INTERVAL_HOURS=12

# How old a mount should be before considering it orphaned (in hours)
CITADEL_MOUNT_MAX_AGE_HOURS=24

# Whether to automatically unmount orphaned mounts
CITADEL_AUTO_UNMOUNT_ORPHANED=true
```

## Using the File Browser

When you mount an archive through the web interface, you can:

1. **Browse Files and Folders**: Navigate through the archive structure
2. **Download Individual Files**: Click on any file to download it
3. **Download Folders**: Click the download button next to any folder to download it as a ZIP
4. **Multi-select Files/Folders**: Select multiple items using checkboxes
5. **Batch Download**: Download all selected items as a single ZIP file

### Multi-select Features

The file browser includes several features to make selecting and downloading multiple items easier:

- **Select All/Deselect All buttons**: Quickly select or deselect all files in the current directory
- **Selection Counter**: Shows how many items are currently selected
- **Smart ZIP Creation**: Creates organized ZIP archives with proper folder structure

## CLI Commands

Citadel provides several CLI commands for mount management:

```bash
# List all active mounts
flask mounts list

# List orphaned mounts
flask mounts list-orphaned --hours=24

# Clean up orphaned mounts
flask mounts cleanup --hours=24 --force

# List all system Borg mounts
flask mounts system-list

# Force unmount all Borg mounts (use with caution!)
flask mounts force-unmount-all

# Dump debug information about mounts
flask mounts debug-info
```

## Admin Interface

Administrators can access the mount management interface at `/backup/admin/mounts`. This interface provides:

1. List of all active mounts
2. List of orphaned mounts
3. List of system Borg mounts
4. Tools for unmounting individual mounts
5. Tools for batch unmounting orphaned mounts
6. Emergency force unmount capability for stuck mounts
