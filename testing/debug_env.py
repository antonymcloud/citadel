#!/usr/bin/env python3
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Print DEBUG value
if os.environ.get('DEBUG') == "True":
    debug_env = True
    debug_bool = True
else:
    debug_env = False
    debug_bool = False


#debug_env = os.environ.get('DEBUG', 'Not Set')
#debug_bool = debug_env.lower() in ('true', '1', 't')

print(f"DEBUG environment variable: '{debug_env}'")
print(f"Evaluates to boolean: {debug_bool}")

# Print paths
borg_paths = ["/usr/bin/borg", "/usr/local/bin/borg"]
for path in borg_paths:
    exists = os.path.exists(path)
    print(f"Path '{path}' exists: {exists}")
