"""Simple Chart.js chart generator for Flask."""

import json
from markupsafe import Markup
from flask import render_template_string

class SimpleChart:
    """A simple Chart.js chart generator for Flask."""
    
    def __init__(self, chart_id=None, chart_type="line", data=None, options=None, width=None, height=400):
        """Initialize a chart.
        
        Args:
            chart_id: Unique identifier for the chart.
            chart_type: Type of chart (line, bar, pie, etc.)
            data: Chart data.
            options: Chart options.
            width: Chart width.
            height: Chart height.
        """
        self.chart_id = chart_id or f"chart_{id(self)}"
        self.chart_type = chart_type
        self.height = height
        self.width = width
        self.data = data or {"labels": [], "datasets": []}
        self.options = options or {}
    
    def render(self):
        """Render the chart HTML and JavaScript."""
        chart_config = {
            "type": self.chart_type,
            "data": self.data,
            "options": self.options
        }
        
        # Add debug info directly to the chart to better diagnose issues
        html = f"""
        <div class="chart-container" style="position: relative; height: {self.height}px; {'width: ' + str(self.width) + 'px;' if self.width else 'width: 100%;'}">
            <canvas id="{self.chart_id}"></canvas>
            <div id="{self.chart_id}_debug" class="chart-debug" style="display: none;">
                <pre style="font-size: 10px; overflow: auto; max-height: 200px;">{json.dumps(chart_config, indent=2)}</pre>
            </div>
            <div id="{self.chart_id}_error" class="chart-error d-none">
                <div class="alert alert-danger">
                    <i class="fas fa-exclamation-circle me-2"></i>
                    Chart rendering failed. Please ensure Chart.js is loaded.
                </div>
            </div>
        </div>
        <script>
            (function() {{
                console.log('Initializing chart: {self.chart_id}');
                console.log('Chart config:', {json.dumps(chart_config)});
                
                function renderChart() {{
                    try {{
                        if (typeof Chart === 'undefined') {{
                            console.error('Chart.js not loaded for {self.chart_id}');
                            document.getElementById('{self.chart_id}_error').classList.remove('d-none');
                            return;
                        }}
                        var ctx = document.getElementById('{self.chart_id}').getContext('2d');
                        new Chart(ctx, {json.dumps(chart_config)});
                        console.log('Chart {self.chart_id} rendered successfully');
                    }} catch (e) {{
                        console.error('Error rendering chart {self.chart_id}:', e);
                        document.getElementById('{self.chart_id}_error').classList.remove('d-none');
                    }}
                }}
                
                // Ensure the DOM is loaded before trying to render the chart
                if (document.readyState === 'loading') {{
                    document.addEventListener('DOMContentLoaded', renderChart);
                }} else {{
                    renderChart();
                }}
            }})();
        </script>
        """
        return Markup(html)
    
    def html_only(self):
        """Render only the HTML container for the chart."""
        style = f"height: {self.height}px;"
        if self.width:
            style += f" width: {self.width}px;"
        
        return Markup(f'<div style="{style}"><canvas id="{self.chart_id}"></canvas></div>')
    
    def script_only(self):
        """Render only the JavaScript for the chart."""
        chart_config = {
            "type": self.chart_type,
            "data": self.data,
            "options": self.options
        }
        
        script = f"""
        <script>
            document.addEventListener('DOMContentLoaded', function() {{
                var ctx = document.getElementById('{self.chart_id}').getContext('2d');
                new Chart(ctx, {json.dumps(chart_config)});
            }});
        </script>
        """
        return Markup(script)

def create_line_chart(chart_id, labels, datasets, title=None, x_label=None, y_label=None, height=400):
    """Create a line chart.
    
    Args:
        chart_id: Unique identifier for the chart.
        labels: X-axis labels.
        datasets: List of datasets, each with at least 'data' and 'label' keys.
        title: Chart title.
        x_label: X-axis label.
        y_label: Y-axis label.
        height: Chart height.
    
    Returns:
        A SimpleChart instance.
    """
    options = {
        "responsive": True,
        "maintainAspectRatio": True,
        "plugins": {},
        "layout": {
            "padding": {
                "top": 10,
                "right": 10,
                "bottom": 10,
                "left": 10
            }
        }
    }
    
    if title:
        options["plugins"]["title"] = {
            "display": True,
            "text": title
        }
    
    if x_label or y_label:
        options["scales"] = {}
        
        if x_label:
            options["scales"]["x"] = {
                "title": {
                    "display": True,
                    "text": x_label
                }
            }
        
        if y_label:
            options["scales"]["y"] = {
                "title": {
                    "display": True,
                    "text": y_label
                }
            }
    
    data = {
        "labels": labels,
        "datasets": datasets
    }
    
    return SimpleChart(chart_id=chart_id, chart_type="line", data=data, options=options, height=height)

def create_bar_chart(chart_id, labels, datasets, title=None, x_label=None, y_label=None, height=400):
    """Create a bar chart."""
    chart = create_line_chart(chart_id, labels, datasets, title, x_label, y_label, height)
    chart.chart_type = "bar"
    return chart

def create_pie_chart(chart_id, labels, data, title=None, height=400):
    """Create a pie chart."""
    options = {
        "responsive": True,
        "maintainAspectRatio": True,
        "plugins": {
            "legend": {
                "position": "bottom"
            }
        }
    }
    
    if title:
        options["plugins"]["title"] = {
            "display": True,
            "text": title
        }
    
    # Extract colors if provided in data
    colors = []
    values = []
    
    for item in data:
        if isinstance(item, dict):
            values.append(item.get("value", 0))
            if "color" in item:
                colors.append(item["color"])
        else:
            values.append(item)
    
    datasets = [{
        "data": values,
        "backgroundColor": colors if colors else None
    }]
    
    chart_data = {
        "labels": labels,
        "datasets": datasets
    }
    
    return SimpleChart(chart_id=chart_id, chart_type="pie", data=chart_data, options=options, height=height)
