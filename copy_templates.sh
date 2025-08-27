#!/bin/bash
# Script to copy templates to the package directory

# Create template directories
mkdir -p towerofborg/templates/auth
mkdir -p towerofborg/templates/backup
mkdir -p towerofborg/templates/common
mkdir -p towerofborg/templates/errors
mkdir -p towerofborg/templates/schedule
mkdir -p towerofborg/templates/source

# Copy templates
cp -r templates/auth/* towerofborg/templates/auth/
cp -r templates/backup/* towerofborg/templates/backup/
cp -r templates/common/* towerofborg/templates/common/
cp -r templates/schedule/* towerofborg/templates/schedule/
cp -r templates/source/* towerofborg/templates/source/

# Create error templates if they don't exist
if [ ! -d "templates/errors" ]; then
    mkdir -p towerofborg/templates/errors
    
    # Create 404 template
    cat > towerofborg/templates/errors/404.html << 'EOF'
{% extends "common/base.html" %}

{% block title %}Page Not Found{% endblock %}

{% block content %}
<div class="container">
    <div class="row">
        <div class="col-md-12 text-center">
            <h1 class="mt-5">404 - Page Not Found</h1>
            <p class="lead">The page you are looking for does not exist.</p>
            <a href="{{ url_for('dashboard') }}" class="btn btn-primary">Return to Dashboard</a>
        </div>
    </div>
</div>
{% endblock %}
EOF

    # Create 500 template
    cat > towerofborg/templates/errors/500.html << 'EOF'
{% extends "common/base.html" %}

{% block title %}Server Error{% endblock %}

{% block content %}
<div class="container">
    <div class="row">
        <div class="col-md-12 text-center">
            <h1 class="mt-5">500 - Server Error</h1>
            <p class="lead">Something went wrong on our end. Please try again later.</p>
            <a href="{{ url_for('dashboard') }}" class="btn btn-primary">Return to Dashboard</a>
        </div>
    </div>
</div>
{% endblock %}
EOF
fi

echo "Templates copied to towerofborg/templates/"
