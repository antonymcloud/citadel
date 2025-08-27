#!/bin/bash
# Script to test the new package structure

# Rename original app.py to app.py.old
mv app.py app.py.old

# Rename app.py.new to app.py
mv app.py.new app.py

# Run the application
echo "Starting Tower of Borg with new package structure..."
python app.py
