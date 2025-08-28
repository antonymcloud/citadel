"""Compatibility layer for flask_charts with newer Jinja2 versions."""

try:
    # Try the original import first
    from flask_charts import Chart, BarChart, LineChart, PieChart
except ImportError:
    # If that fails, create our own compatibility layer
    import json
    from markupsafe import Markup
    from flask import current_app

    class Chart:
        """Base chart class for compatibility with flask_charts."""
        
        def __init__(self, name=None, options=None, height=400, data=None):
            self.name = name or f"chart_{id(self)}"  # Generate a unique name if none provided
            self.options = options or {}
            self.height = height
            self.chart_type = "bar"  # default
            self.data = {"labels": [], "datasets": []}
            self.labels = []
            self.title = ""
            self.xlabel = ""
            self.ylabel = ""
            self.color = "#36a2eb"
            self.fill = False
            self.width = 100
            
            # If data is provided directly, add it as a dataset
            if data:
                self.add_dataset(data, label=self.title, backgroundColor=self.color, 
                                borderColor=self.color, fill=self.fill)
            
        def add_dataset(self, data, **kwargs):
            """Add a dataset to the chart."""
            dataset = {"data": data}
            dataset.update(kwargs)
            self.data["datasets"].append(dataset)
            return self
            
        def set_labels(self, labels):
            """Set the labels for the chart."""
            self.data["labels"] = labels
            return self
            
        def render(self):
            """Render the chart as HTML markup."""
            # Update labels from the instance variable
            self.data["labels"] = self.labels
            
            # Update options based on properties
            if not self.options.get("title") and self.title:
                if "plugins" not in self.options:
                    self.options["plugins"] = {}
                if "title" not in self.options["plugins"]:
                    self.options["plugins"]["title"] = {}
                self.options["plugins"]["title"]["display"] = True
                self.options["plugins"]["title"]["text"] = self.title
            
            # Add axes labels if provided
            if self.xlabel or self.ylabel:
                if "scales" not in self.options:
                    self.options["scales"] = {}
                if self.xlabel and "x" not in self.options["scales"]:
                    self.options["scales"]["x"] = {"title": {"display": True, "text": self.xlabel}}
                if self.ylabel and "y" not in self.options["scales"]:
                    self.options["scales"]["y"] = {"title": {"display": True, "text": self.ylabel}}
                    
            chart_json = json.dumps({
                "type": self.chart_type,
                "data": self.data,
                "options": self.options
            })
            
            html = f"""
            <div style="height: {self.height}px;">
                <canvas id="{self.name}"></canvas>
            </div>
            <script>
                document.addEventListener('DOMContentLoaded', function() {{
                    var ctx = document.getElementById('{self.name}').getContext('2d');
                    new Chart(ctx, {chart_json});
                }});
            </script>
            """
            return Markup(html)
            
        def html(self):
            """Return the HTML container part of the chart."""
            return Markup(f'<div style="height: {self.height}px;"><canvas id="{self.name}"></canvas></div>')
            
        def script(self):
            """Return just the JavaScript part of the chart."""
            # Update labels from the instance variable
            self.data["labels"] = self.labels
            
            # Update options based on properties
            if not self.options.get("title") and self.title:
                if "plugins" not in self.options:
                    self.options["plugins"] = {}
                if "title" not in self.options["plugins"]:
                    self.options["plugins"]["title"] = {}
                self.options["plugins"]["title"]["display"] = True
                self.options["plugins"]["title"]["text"] = self.title
            
            # Add axes labels if provided
            if self.xlabel or self.ylabel:
                if "scales" not in self.options:
                    self.options["scales"] = {}
                if self.xlabel and "x" not in self.options["scales"]:
                    self.options["scales"]["x"] = {"title": {"display": True, "text": self.xlabel}}
                if self.ylabel and "y" not in self.options["scales"]:
                    self.options["scales"]["y"] = {"title": {"display": True, "text": self.ylabel}}
                    
            chart_json = json.dumps({
                "type": self.chart_type,
                "data": self.data,
                "options": self.options
            })
            
            script = f"""
            <script>
                document.addEventListener('DOMContentLoaded', function() {{
                    var ctx = document.getElementById('{self.name}').getContext('2d');
                    new Chart(ctx, {chart_json});
                }});
            </script>
            """
            return Markup(script)

    class BarChart(Chart):
        """Bar chart implementation."""
        
        def __init__(self, name=None, options=None, height=400, data=None):
            super().__init__(name, options, height, data)
            self.chart_type = "bar"

    class LineChart(Chart):
        """Line chart implementation."""
        
        def __init__(self, name=None, options=None, height=400, data=None):
            super().__init__(name, options, height, data)
            self.chart_type = "line"

    class PieChart(Chart):
        """Pie chart implementation."""
        
        def __init__(self, name=None, options=None, height=400, data=None):
            super().__init__(name, options, height, data)
            self.chart_type = "pie"
