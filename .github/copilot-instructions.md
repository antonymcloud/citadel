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
- **Models**: SQLAlchemy ORM models for Repository, Job, Source, User, etc.
- **Routes**: Organized in Blueprint modules (backup_bp, auth_bp, etc.)
- **Templates**: Jinja2 templates in the templates/ directory
- **Static Files**: CSS, JS in the static/ directory
- **Migrations**: Manual migration scripts for database schema changes

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
1. The `extract_stats_from_output` function parses Borg command output
2. Handle both regular output and output with [WARN] prefixes
3. Check for zero values before calculating ratios to avoid division by zero
4. Extract all available metrics including:
   - Archive name and fingerprint
   - Start and end times
   - Duration in seconds
   - Number of files
   - Original, compressed, and deduplicated sizes
   - Compression and deduplication ratios

### Statistics Display
1. Use Bootstrap cards and tables for statistics display
2. Include progress bars for compression ratio visualization
3. Format file sizes with appropriate units (KB, MB, GB)
4. Display timestamps in a user-friendly format
5. Calculate and display derived metrics (compression ratio, etc.)

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

## Common Issues and Solutions
1. SQLAlchemy metadata conflict: Use 'job_metadata' instead of 'metadata'
2. Borg output parsing: Handle both standard output and output with [WARN] prefixes
3. Division by zero: Check for zero values before calculating ratios
4. Template rendering: Ensure all variables exist before rendering
5. Indentation errors: Be careful with indentation in Python code

## Best Practices for Feature Development
1. Break down changes into small, testable units
2. Test statistics extraction independently before integrating
3. Update templates to handle missing or incomplete data gracefully
4. Add debug output to help diagnose issues
5. Handle edge cases (empty output, zero values, etc.)
