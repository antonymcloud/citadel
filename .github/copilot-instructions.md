# Tower of Borg Project Guidelines

## Project Overview
Tower of Borg is a Flask web application that provides a web-based interface for managing Borg backup repositories. It allows users to create, monitor, and manage backup jobs, as well as view statistics from completed backups.

## Key Technical Details

### Core Technologies
- **Backend**: Python 3 with Flask web framework
- **Database**: SQLite with SQLAlchemy ORM
- **Authentication**: Flask-Login
- **Templating**: Jinja2
- **Frontend**: Bootstrap for UI components
- **Backup Engine**: Borg Backup (real or mock implementation)

### Project Structure
- **Application Factory**: Uses Flask's application factory pattern in `towerofborg/__init__.py`
- **Package-based Organization**: Modular structure with subdirectories for each component
- **Models**: SQLAlchemy ORM models in `towerofborg/models/` directory
- **Blueprints**: Separate blueprint modules (backup, auth, schedules, sources) in their respective directories
- **Templates**: Jinja2 templates in the `towerofborg/templates/` directory
- **Static Files**: CSS, JS in the root `static/` directory
- **Migrations**: Manual migration scripts for database schema changes

### Module Organization
- **towerofborg/**: Main package containing all application code
  - **auth/**: Authentication related routes and utilities
  - **backup/**: Backup and repository management functionality
  - **models/**: Database models for all entities
  - **schedules/**: Schedule management for automated backups
  - **sources/**: Backup source management
  - **utils/**: Shared utility functions and helpers
  - **templates/**: Template files organized by module

## Coding Standards

### Python Style Guidelines
1. Follow PEP 8 conventions for Python code
2. Use 4 spaces for indentation (not tabs)
3. Keep line length under 100 characters
4. Use descriptive variable and function names
5. Include docstrings for functions and classes

### Database Guidelines
1. Use SQLAlchemy ORM for database operations
2. Avoid direct SQL queries when possible
3. Use migrations for database schema changes
4. Avoid using SQLAlchemy reserved attribute names (e.g., 'metadata')
5. Use 'job_metadata' instead of 'metadata' for Job model

### Error Handling
1. Use try/except blocks for error-prone operations
2. Log errors with appropriate context
3. Provide user-friendly error messages
4. Include debugging information in development mode

### Testing
1. Write test cases for critical functionality
2. Test data extraction and parsing logic separately
3. Use mock data for testing Borg backup commands
4. Verify statistics extraction with various output formats

## Statistics Handling

### Statistics Extraction
1. The `extract_stats_from_output` function in `towerofborg/backup/utils.py` parses Borg command output
2. Handle both regular output and output with [WARN] prefixes
3. Check for zero values before calculating ratios to avoid division by zero
4. Extract all available metrics including:
   - Archive name and fingerprint
   - Start and end times
   - Duration in seconds
   - Number of files
   - Original, compressed, and deduplicated sizes
   - Compression and deduplication ratios
5. Store sizes with their units (e.g., "5.00 GB") and handle in templates accordingly
6. Use pre-calculated ratios for compression and deduplication instead of doing calculations in templates

### Statistics Display
1. Use Bootstrap cards and tables for statistics display
2. Include progress bars for compression ratio visualization
3. Display size values with their original units (e.g., "5.00 GB")
4. Display timestamps in a user-friendly format
5. Calculate and display derived metrics (compression ratio, etc.)
6. Handle missing or empty values gracefully in templates with conditionals

## Security Considerations
1. Store sensitive data (e.g., passphrases) securely
2. Validate user input before processing
3. Use Flask's CSRF protection for forms
4. Implement proper authentication and authorization

## Debugging Tips
1. Add DEBUG level logging for troubleshooting
2. Include print statements with DEBUG prefix for temporary debugging
3. Use debug sections in templates for development
4. Check for None values before accessing attributes or dictionary keys
5. Use the development server's debug mode for detailed error reporting

## Common Issues and Solutions
1. SQLAlchemy metadata conflict: Use 'job_metadata' instead of 'metadata'
2. Borg output parsing: Handle both standard output and output with [WARN] prefixes
3. Division by zero: Check for zero values before calculating ratios
4. Template rendering: Ensure all variables exist before rendering
5. Job metadata handling: Use `job.set_metadata(metadata_dict)` instead of direct assignment
6. Thread handling: Always use app context in background threads
7. String parsing for size values: Handle size values with units like "5.00 GB" appropriately

## Best Practices for Feature Development
1. Follow the application factory pattern for new components
2. Use blueprints for organizing related routes
3. Place models in the appropriate models/ subdirectory
4. Create module-specific utility functions in their respective directories
5. For shared functionality, use the utils/ directory
6. Test statistics extraction independently before integrating
7. Update templates to handle missing or incomplete data gracefully
8. Add debug output to help diagnose issues
9. Handle edge cases (empty output, zero values, etc.)

## Application Architecture

### Application Factory
The application is structured using Flask's application factory pattern. The main factory function `create_app()` is located in `towerofborg/__init__.py` and handles:

1. Loading configuration from environment variables
2. Initializing database and extensions
3. Registering blueprints
4. Setting up error handlers and context processors

### Blueprint Initialization
Each functional area of the application is implemented as a blueprint and initialized in the factory:

```python
from towerofborg.auth import init_auth, auth_bp
from towerofborg.backup import init_backup, backup_bp
from towerofborg.sources import init_sources, sources_bp
from towerofborg.schedules import init_schedules, schedules_bp

# Initialize modules
init_auth(app)
init_backup(app)
init_sources(app)
init_schedules(app)
```

### Running Background Jobs
When running background jobs that need to access the database:

1. Always pass the application instance to the thread function
2. Create an application context within the thread
3. Use the context manager to ensure proper cleanup:

```python
def _run_job_thread(job_id, app):
    with app.app_context():
        # Access database models and perform operations
```
