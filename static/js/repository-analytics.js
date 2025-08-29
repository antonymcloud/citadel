$(document).ready(function() {
    // Format file sizes for display
    function formatSize(bytes) {
        if (bytes === 0 || bytes === null || bytes === undefined) return '0 Bytes';
        
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }
    
    // Format percentages with 1 decimal place
    function formatPercent(value) {
        if (value === null || value === undefined) return '0%';
        return value.toFixed(1) + '%';
    }
    
    // Format dates nicely
    function formatDate(dateString) {
        if (!dateString) return 'Never';
        
        const date = new Date(dateString);
        return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
    }
    
    // Set progress bar width and text
    function setProgressBar(id, percent) {
        const bar = document.getElementById(id);
        if (bar) {
            bar.style.width = percent + '%';
            bar.setAttribute('aria-valuenow', percent);
            
            // Set the label if it exists
            const label = document.getElementById(id + '-label');
            if (label) {
                label.textContent = formatPercent(percent);
            } else {
                bar.textContent = formatPercent(percent);
            }
        }
    }
    
    // Analytics functions
    function loadAnalytics() {
        $('#analytics-loading').removeClass('d-none');
        $('#analytics-content').addClass('d-none');
        
        // Load repository statistics
        $.ajax({
            url: repoStatsApiUrl,
            type: 'GET',
            dataType: 'json',
            success: function(stats) {
                console.log("Stats loaded successfully:", stats);
                
                try {
                    // Convert any "None" string values to null
                    Object.keys(stats).forEach(key => {
                        if (stats[key] === "None") {
                            stats[key] = null;
                        }
                        
                        // Also check nested objects in size_trend
                        if (key === 'size_trend' && Array.isArray(stats[key])) {
                            stats[key].forEach(point => {
                                Object.keys(point).forEach(pointKey => {
                                    if (point[pointKey] === "None") {
                                        point[pointKey] = null;
                                    }
                                });
                            });
                        }
                    });
                    
                    updateAnalyticsDisplay(stats);
                    
                    // Load the growth chart
                    loadGrowthChart();
                    
                    // Load the frequency chart
                    loadFrequencyChart();
                    
                    // Create success rate chart
                    createSuccessRateChart(stats.successful_jobs, stats.failed_jobs);
                    
                    // Also load forecast data
                    $.ajax({
                        url: repoForecastApiUrl,
                        type: 'GET',
                        dataType: 'json',
                        success: function(forecast) {
                            console.log("Forecast loaded successfully:", forecast);
                            
                            // Convert any "None" string values to null
                            Object.keys(forecast).forEach(key => {
                                if (forecast[key] === "None") {
                                    forecast[key] = null;
                                }
                            });
                            
                            updateForecastDisplay(forecast);
                        },
                        error: function(xhr, status, error) {
                            console.error('Failed to load forecast data:', error);
                            console.error('Response:', xhr.responseText);
                            
                            // Still show analytics without forecast
                            $('#forecast-section').hide();
                        }
                    });
                } catch (e) {
                    console.error("Error processing analytics data:", e);
                    $('#analytics-loading').addClass('d-none');
                    $('#analytics-content').removeClass('d-none').html(`
                        <div class="alert alert-danger">
                            <h5><i class="fas fa-exclamation-circle"></i> Error loading analytics</h5>
                            <p>There was a problem processing the analytics data. Please try again later.</p>
                            <p><small>Technical details: ${e.message}</small></p>
                        </div>
                    `);
                }
                
                // Finally, always show the content and hide the loading indicator, even if there was an error
                setTimeout(function() {
                    $('#analytics-loading').addClass('d-none');
                    $('#analytics-content').removeClass('d-none');
                }, 500);
            },
            error: function(xhr, status, error) {
                console.error('Failed to load analytics data:', error);
                console.error('Response:', xhr.responseText);
                
                // Show an error message in the analytics section
                $('#analytics-loading').addClass('d-none');
                $('#analytics-content').removeClass('d-none');
                
                // Add error alert
                $('.card-body', $('#analytics-content').closest('.card')).prepend(
                    '<div class="alert alert-danger">' +
                    '<i class="fas fa-exclamation-circle me-2"></i>' +
                    'Failed to load analytics data: ' + error +
                    '</div>'
                );
            }
        });
    }
    
    function loadGrowthChart() {
        console.log("Loading growth chart...");
        $.ajax({
            url: repoGrowthChartUrl,
            type: 'GET',
            dataType: 'json',
            success: function(response) {
                console.log("Growth chart response:", response);
                
                // Check if we have data to show in the new format
                if (response.growth_data && response.growth_data.labels && response.growth_data.data && 
                    response.growth_data.labels.length >= 2 && response.growth_data.data.length >= 2) {
                    
                    // We have structured data in the new format, create a chart
                    $('#growth-chart-no-data').addClass('d-none');
                    
                    // Prepare the container with a fresh canvas
                    $('#growth-chart-container').html('<canvas id="growth-chart"></canvas>');
                    
                    // Create the chart with the provided data
                    const ctx = document.getElementById('growth-chart').getContext('2d');
                    growthChart = new Chart(ctx, {
                        type: 'line',
                        data: {
                            labels: response.growth_data.labels,
                            datasets: [{
                                label: 'Repository Size (GB)',
                                data: response.growth_data.data,
                                backgroundColor: 'rgba(54, 162, 235, 0.2)',
                                borderColor: 'rgba(54, 162, 235, 1)',
                                borderWidth: 2,
                                tension: 0.3,
                                fill: true
                            }]
                        },
                        options: {
                            responsive: true,
                            maintainAspectRatio: false,
                            scales: {
                                y: {
                                    beginAtZero: true,
                                    title: {
                                        display: true,
                                        text: 'Size (GB)'
                                    }
                                },
                                x: {
                                    title: {
                                        display: true,
                                        text: 'Date'
                                    }
                                }
                            },
                            plugins: {
                                tooltip: {
                                    callbacks: {
                                        title: function(tooltipItems) {
                                            return tooltipItems[0].label;
                                        },
                                        label: function(context) {
                                            let label = response.growth_data.tooltips ? 
                                                        response.growth_data.tooltips[context.dataIndex] || '' : '';
                                            let value = context.raw;
                                            
                                            if (label) {
                                                return `${label}: ${value.toFixed(2)} GB`;
                                            } else {
                                                return `${value.toFixed(2)} GB`;
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    });
                    
                    // If it's sample data, show a note
                    if (response.is_sample_data) {
                        $('#growth-chart-container').append(
                            '<div class="alert alert-info mt-3 text-center">' +
                            '<i class="fas fa-info-circle me-2"></i>' +
                            'This is sample data. Create more backups to see actual growth.' +
                            '</div>'
                        );
                    }
                }
                // Fallback to the old format if new format isn't available
                else if (!response.is_sample_data && response.chart_data && response.chart_data.length >= 2) {
                    // We have real data in the old format, create a chart
                    $('#growth-chart-no-data').addClass('d-none');
                    
                    // Prepare the container with a fresh canvas
                    $('#growth-chart-container').html('<canvas id="growth-chart"></canvas>');
                    
                    // Extract data for the chart
                    const labels = response.chart_data.map(d => d.date);
                    const values = response.chart_data.map(d => {
                        // If size is a string like "5.00 GB", extract the numeric value
                        if (typeof d.size === 'string') {
                            const parts = d.size.split(' ');
                            if (parts.length === 2) {
                                return parseFloat(parts[0]);
                            }
                        }
                        return d.size;
                    });
                    
                    // Create the chart
                    const ctx = document.getElementById('growth-chart').getContext('2d');
                    growthChart = new Chart(ctx, {
                        type: 'line',
                        data: {
                            labels: labels,
                            datasets: [{
                                label: 'Repository Size',
                                data: values,
                                backgroundColor: 'rgba(54, 162, 235, 0.2)',
                                borderColor: 'rgba(54, 162, 235, 1)',
                                borderWidth: 2,
                                tension: 0.3,
                                fill: true
                            }]
                        },
                        options: {
                            responsive: true,
                            maintainAspectRatio: false,
                            scales: {
                                y: {
                                    beginAtZero: true,
                                    title: {
                                        display: true,
                                        text: 'Size'
                                    }
                                },
                                x: {
                                    title: {
                                        display: true,
                                        text: 'Date'
                                    }
                                }
                            }
                        }
                    });
                    
                    // If it's sample data, show a note
                    if (response.is_sample_data) {
                        $('#growth-chart-container').append(
                            '<div class="alert alert-info mt-3 text-center">' +
                            '<i class="fas fa-info-circle me-2"></i>' +
                            'This is sample data. Create more backups to see actual growth.' +
                            '</div>'
                        );
                    }
                } else if (response.chart_html) {
                    // Fallback to server-rendered HTML if available
                    $('#growth-chart-container').html(response.chart_html);
                    $('#growth-chart-no-data').addClass('d-none');
                    
                    // If it's sample data, show a note
                    if (response.is_sample_data) {
                        $('#growth-chart-container').append(
                            '<div class="alert alert-info mt-3 text-center">' +
                            '<i class="fas fa-info-circle me-2"></i>' +
                            'This is sample data. Create more backups to see actual growth.' +
                            '</div>'
                        );
                    }
                } else {
                    // Show no data message
                    $('#growth-chart-container').empty();
                    $('#growth-chart-no-data').removeClass('d-none');
                }
            },
            error: function(xhr, status, error) {
                console.error('Failed to load growth chart:', error);
                
                // Show error message
                $('#growth-chart-container').html(
                    '<div class="alert alert-danger">' +
                    '<i class="fas fa-exclamation-circle me-2"></i>' +
                    'Failed to load growth chart: ' + error +
                    '</div>'
                );
            }
        });
    }
    
    function loadFrequencyChart() {
        console.log("Loading frequency chart...");
        $.ajax({
            url: repoFrequencyChartUrl,
            type: 'GET',
            dataType: 'json',
            success: function(response) {
                console.log("Frequency chart response:", response);
                
                // Check for chart data in the response
                if (response.frequency_data && (response.frequency_data.by_day || response.frequency_data.by_hour)) {
                    // Clear containers and show charts
                    $('#frequency-chart-container').html('<div class="row"><div class="col-md-6 mb-3"><h6 class="card-subtitle mb-2">Backups by Day of Week</h6><div id="frequency-day-chart-container"><canvas id="frequency-day-chart"></canvas></div></div><div class="col-md-6 mb-3"><h6 class="card-subtitle mb-2">Backups by Hour of Day</h6><div id="frequency-hour-chart-container"><canvas id="frequency-hour-chart"></canvas></div></div></div>');
                    $('#frequency-chart-no-data').addClass('d-none');
                    
                    // Create day of week frequency chart
                    if (response.frequency_data.by_day && response.frequency_data.by_day.labels && response.frequency_data.by_day.data) {
                        // Ensure canvas is recreated to avoid errors
                        const dayCtx = document.getElementById('frequency-day-chart').getContext('2d');
                        frequencyDayChart = new Chart(dayCtx, {
                            type: 'bar',
                            data: {
                                labels: response.frequency_data.by_day.labels,
                                datasets: [{
                                    label: 'Backups',
                                    data: response.frequency_data.by_day.data,
                                    backgroundColor: 'rgba(54, 162, 235, 0.6)',
                                    borderColor: 'rgba(54, 162, 235, 1)',
                                    borderWidth: 1
                                }]
                            },
                            options: {
                                responsive: true,
                                maintainAspectRatio: false,
                                scales: {
                                    y: {
                                        beginAtZero: true,
                                        title: {
                                            display: true,
                                            text: 'Number of Backups'
                                        }
                                    },
                                    x: {
                                        title: {
                                            display: true,
                                            text: 'Day of Week'
                                        }
                                    }
                                }
                            }
                        });
                    }
                    
                    // Create hour of day frequency chart
                    if (response.frequency_data.by_hour && response.frequency_data.by_hour.labels && response.frequency_data.by_hour.data) {
                        // Ensure canvas is recreated to avoid errors
                        const hourCtx = document.getElementById('frequency-hour-chart').getContext('2d');
                        frequencyHourChart = new Chart(hourCtx, {
                            type: 'bar',
                            data: {
                                labels: response.frequency_data.by_hour.labels,
                                datasets: [{
                                    label: 'Backups',
                                    data: response.frequency_data.by_hour.data,
                                    backgroundColor: 'rgba(75, 192, 192, 0.6)',
                                    borderColor: 'rgba(75, 192, 192, 1)',
                                    borderWidth: 1
                                }]
                            },
                            options: {
                                responsive: true,
                                maintainAspectRatio: false,
                                scales: {
                                    y: {
                                        beginAtZero: true,
                                        title: {
                                            display: true,
                                            text: 'Number of Backups'
                                        }
                                    },
                                    x: {
                                        title: {
                                            display: true,
                                            text: 'Hour of Day'
                                        }
                                    }
                                }
                            }
                        });
                    }
                    
                    // If it's sample data, show a note
                    if (response.is_sample_data) {
                        $('#frequency-chart-container').append(
                            '<div class="alert alert-info mt-3 text-center">' +
                            '<i class="fas fa-info-circle me-2"></i>' +
                            'This is sample data. Create more backups to see actual frequency.' +
                            '</div>'
                        );
                    }
                } else if (response.chart_html) {
                    // Fallback to server-rendered HTML if available
                    $('#frequency-chart-container').html(response.chart_html);
                    $('#frequency-chart-no-data').addClass('d-none');
                    
                    // If it's sample data, show a note
                    if (response.is_sample_data) {
                        $('#frequency-chart-container').append(
                            '<div class="alert alert-info mt-3 text-center">' +
                            '<i class="fas fa-info-circle me-2"></i>' +
                            'This is sample data. Create more backups to see actual frequency.' +
                            '</div>'
                        );
                    }
                } else {
                    // Show no data message
                    $('#frequency-chart-container').empty();
                    $('#frequency-chart-no-data').removeClass('d-none');
                }
            },
            error: function(xhr, status, error) {
                console.error('Failed to load frequency chart:', error);
                
                // Show error message
                $('#frequency-chart-container').html(
                    '<div class="alert alert-danger">' +
                    '<i class="fas fa-exclamation-circle me-2"></i>' +
                    'Failed to load frequency chart: ' + error +
                    '</div>'
                );
            }
        });
    }
    
    function createSuccessRateChart(successCount, failedCount) {
        if (!successCount && !failedCount) {
            $('#success-chart-no-data').removeClass('d-none');
            $('#success-rate-container').empty();
            return;
        }
        
        // Make sure we have numeric values
        successCount = parseInt(successCount) || 0;
        failedCount = parseInt(failedCount) || 0;
        
        if (successCount === 0 && failedCount === 0) {
            $('#success-chart-no-data').removeClass('d-none');
            $('#success-rate-container').empty();
            return;
        }
        
        // Hide the no data message
        $('#success-chart-no-data').addClass('d-none');
        
        // Destroy existing chart if it exists
        if (successRateChart) {
            successRateChart.destroy();
            successRateChart = null;
        }
        
        // Ensure canvas is recreated to avoid errors
        $('#success-rate-container').html('<canvas id="success-rate-chart"></canvas>');
        
        const ctx = document.getElementById('success-rate-chart').getContext('2d');
        successRateChart = new Chart(ctx, {
            type: 'pie',
            data: {
                labels: ['Successful', 'Failed'],
                datasets: [{
                    data: [successCount, failedCount],
                    backgroundColor: ['#28a745', '#dc3545'],
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom'
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                const label = context.label || '';
                                const value = context.raw || 0;
                                const total = successCount + failedCount;
                                const percentage = Math.round((value / total) * 100);
                                return `${label}: ${value} (${percentage}%)`;
                            }
                        }
                    }
                }
            }
        });
    }
    
    function updateAnalyticsDisplay(stats) {
        // Update stats display
        $('#latest-size').text(stats.latest_size || '0 GB');
        $('#space-usage').text(stats.space_usage ? formatPercent(stats.space_usage) : '0%');
        $('#archives-count').text(stats.archive_count || '0');
        
        // Update the usage bar
        const usagePercent = stats.space_usage || 0;
        setProgressBar('usage-bar', usagePercent);
        
        // Update backup statistics
        $('#total-backups').text(stats.total_jobs || '0');
        $('#successful-backups').text(stats.successful_jobs || '0');
        $('#failed-backups').text(stats.failed_jobs || '0');
        
        // Calculate success rate
        const totalJobs = parseInt(stats.total_jobs) || 0;
        const successfulJobs = parseInt(stats.successful_jobs) || 0;
        let successRate = 0;
        if (totalJobs > 0) {
            successRate = (successfulJobs / totalJobs) * 100;
        }
        $('#success-rate').text(formatPercent(successRate));
        
        // Update other stats
        $('#average-size').text(stats.average_size || 'Unknown');
        $('#average-compression').text(stats.average_compression ? formatPercent(stats.average_compression) : 'Unknown');
        $('#last-backup').text(formatDate(stats.last_backup_time));
    }
    
    function updateForecastDisplay(forecast) {
        if (!forecast) {
            $('#forecast-section').hide();
            return;
        }
        
        // Set growth rate
        $('#growth-rate-value').text(forecast.growth_rate ? forecast.growth_rate + '/day' : 'Unknown');
        
        // Set full date
        if (forecast.full_date) {
            const fullDate = new Date(forecast.full_date);
            const now = new Date();
            const diffTime = Math.abs(fullDate - now);
            const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
            
            $('#full-date-value').text(formatDate(forecast.full_date));
            $('#full-date-note').text(`Approximately ${diffDays} days from now`);
        } else {
            $('#full-date-value').text('No forecast available');
            $('#full-date-note').text('Not enough data to make a prediction');
        }
        
        // Set current usage
        const currentPercent = forecast.current_percent || 0;
        setProgressBar('current-usage-bar', currentPercent);
        
        // Set forecasts
        if (forecast.forecast_1m) {
            $('#forecast-1m').text(forecast.forecast_1m.size || 'Unknown');
            setProgressBar('forecast-1m-bar', forecast.forecast_1m.percent || 0);
        }
        
        if (forecast.forecast_3m) {
            $('#forecast-3m').text(forecast.forecast_3m.size || 'Unknown');
            setProgressBar('forecast-3m-bar', forecast.forecast_3m.percent || 0);
        }
        
        if (forecast.forecast_6m) {
            $('#forecast-6m').text(forecast.forecast_6m.size || 'Unknown');
            setProgressBar('forecast-6m-bar', forecast.forecast_6m.percent || 0);
        }
    }
    
    // Show error as a toast notification
    function showError(message) {
        console.error(message);
        
        // Create a toast notification
        const toast = `
        <div class="toast-container position-fixed bottom-0 end-0 p-3">
            <div class="toast bg-danger text-white" role="alert" aria-live="assertive" aria-atomic="true">
                <div class="toast-header">
                    <i class="fas fa-exclamation-circle me-2"></i>
                    <strong class="me-auto">Error</strong>
                    <button type="button" class="btn-close" data-bs-dismiss="toast" aria-label="Close"></button>
                </div>
                <div class="toast-body">
                    ${message}
                </div>
            </div>
        </div>`;
        
        // Add toast to body
        $('body').append(toast);
        $('.toast').toast('show');
    }
    
    // Store chart instances for proper cleanup
    let growthChart = null;
    let frequencyDayChart = null;
    let frequencyHourChart = null;
    let successRateChart = null;
    
    // Function to clean up charts before refreshing
    function cleanupCharts() {
        // Destroy existing charts to prevent memory leaks and errors
        if (growthChart) {
            growthChart.destroy();
            growthChart = null;
        }
        
        if (frequencyDayChart) {
            frequencyDayChart.destroy();
            frequencyDayChart = null;
        }
        
        if (frequencyHourChart) {
            frequencyHourChart.destroy();
            frequencyHourChart = null;
        }
        
        if (successRateChart) {
            successRateChart.destroy();
            successRateChart = null;
        }
        
        // Clear chart containers
        $('#growth-chart-container').html('<div class="spinner-border text-primary" role="status"></div><p>Loading growth chart...</p>');
        $('#frequency-chart-container').html('<div class="spinner-border text-primary" role="status"></div><p>Loading frequency chart...</p>');
        $('#success-rate-container').html('<div class="spinner-border text-primary" role="status"></div><p>Loading success rate chart...</p>');
    }
    
    // Initialize analytics
    loadAnalytics();
    
    // Refresh analytics when button is clicked
    $('#refreshAnalytics').click(function() {
        cleanupCharts();
        loadAnalytics();
    });
});
