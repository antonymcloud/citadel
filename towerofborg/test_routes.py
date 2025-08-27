"""Diagnostic routes for testing charts."""

from flask import Blueprint, jsonify, render_template, render_template_string
from towerofborg.utils.simple_charts import create_line_chart, create_bar_chart, create_pie_chart
import logging

# Configure logger
logger = logging.getLogger(__name__)

# Create a test blueprint
test_bp = Blueprint('test', __name__, url_prefix='/test')

@test_bp.route('/chart')
def test_chart():
    """Simple test route to generate a test chart."""
    try:
        # Create a simple line chart
        labels = ['Day 1', 'Day 2', 'Day 3', 'Day 4', 'Day 5']
        data = [10, 20, 30, 25, 40]
        
        datasets = [{
            "label": "Test Data",
            "data": data,
            "borderColor": "#36a2eb",
            "backgroundColor": "rgba(54, 162, 235, 0.2)",
            "fill": True
        }]
        
        line_chart = create_line_chart(
            chart_id="test_line_chart",
            labels=labels,
            datasets=datasets,
            title="Test Line Chart",
            x_label="Days",
            y_label="Values",
            height=300
        )
        
        bar_chart = create_bar_chart(
            chart_id="test_bar_chart",
            labels=labels,
            datasets=datasets,
            title="Test Bar Chart",
            x_label="Days",
            y_label="Values",
            height=300
        )
        
        pie_data = [15, 25, 35, 10, 15]
        pie_chart = create_pie_chart(
            chart_id="test_pie_chart",
            labels=labels,
            data=pie_data,
            title="Test Pie Chart",
            height=300
        )
        
        # Return a simple HTML page with the charts
        return render_template('test/chart.html', 
                               line_chart=line_chart.render(),
                               bar_chart=bar_chart.render(),
                               pie_chart=pie_chart.render())
    except Exception as e:
        logger.error(f"Error in test chart: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@test_bp.route('/ajax_chart')
def ajax_test_chart():
    """Test route for AJAX chart loading."""
    return render_template('test/ajax_chart.html')

@test_bp.route('/get_test_chart')
def get_test_chart():
    """API endpoint to get a test chart via AJAX."""
    logger.debug("Generating test chart for AJAX")
    
    try:
        # Create a simple line chart
        labels = ['Day 1', 'Day 2', 'Day 3', 'Day 4', 'Day 5']
        data = [10, 20, 30, 25, 40]
        
        datasets = [{
            "label": "Test Data",
            "data": data,
            "borderColor": "#4bc0c0",
            "backgroundColor": "rgba(75, 192, 192, 0.2)",
            "fill": True
        }]
        
        chart = create_line_chart(
            chart_id="ajax_test_chart",
            labels=labels,
            datasets=datasets,
            title="AJAX Test Chart",
            x_label="Days",
            y_label="Values",
            height=300
        )
        
        # Return chart HTML in JSON response
        return jsonify({
            "chart_html": chart.render(),
            "is_sample_data": False
        })
    except Exception as e:
        logger.error(f"Error generating test chart: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500
