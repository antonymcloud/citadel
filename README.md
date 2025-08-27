# Tower of Borg

A web interface for Borg backup, allowing you to manage repositories, create backups, schedule automated backups, and more.

## Features

- Create and manage Borg repositories
- Add backup sources (local or remote via SSH)
- Create backups with detailed statistics
- Schedule automated backups (daily, weekly, or monthly)
- View backup history and logs
- Prune old backups with configurable retention policies

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/towerofborg.git
   cd towerofborg
   ```

2. Create a virtual environment and install dependencies:
   ```
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. Configure environment variables (optional):
   Create a `.env` file with the following variables:
   ```
   SECRET_KEY=your-secret-key
   DATABASE_URI=sqlite:///towerofborg.db
   ADMIN_PASSWORD=your-admin-password
   ```

4. Run the application:
   ```
   python app.py
   ```

5. Access the web interface at http://localhost:5000

## Usage

1. Log in with the default admin account (username: admin, password: towerofborg)
2. Create a new repository
3. Add backup sources
4. Create backups manually or set up schedules
5. Monitor backup jobs and statistics

## Project Structure

The project follows a modular structure:

```
towerofborg/
├── auth/            # Authentication related code
├── backup/          # Backup operations and repository management
├── models/          # Database models
├── schedules/       # Scheduling functionality
├── sources/         # Backup source management
├── templates/       # Jinja2 templates
├── utils/           # Utility functions and helpers
└── __init__.py      # Application factory
```

## License

MIT License

## Requirements

- Python 3.7+
- Borg Backup 1.1+
- Flask and extensions (see requirements.txt)
