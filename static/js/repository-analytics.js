$(document).ready(function () {
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

    // Update analytics display function
    function updateAnalyticsDisplay(stats) {
        // Check if we have data, show appropriate alerts for missing data
        const hasData = stats && Object.keys(stats).length > 0;
        if (!hasData) {
            $('.card-body', $('#analytics-content').closest('.card')).prepend(
                '<div class="alert alert-warning">' +
                '<i class="fas fa-exclamation-triangle me-2"></i>' +
                'Limited or no analytics data available. Create more backups to see comprehensive analytics.' +
                '</div>'
            );
            return;
        }

        // Update analytics displays with available data, using defaults for missing data
        $('#latest-size').text(stats.latest_size || 'No data');

        // Handle space usage percentage
        if (stats.space_usage_percent !== null && stats.space_usage_percent !== undefined) {
            $('#space-usage').text(formatPercent(stats.space_usage_percent));
            setProgressBar('usage-bar', stats.space_usage_percent);
        } else {
            $('#space-usage').text('N/A');
            setProgressBar('usage-bar', 0);
        }

        // Max size is from repository settings, should always be available
        $('#max-size').text((stats.max_size || 0) + ' GB');

        // Archives count might be missing if no list job has been run
        $('#archives-count').text(stats.archives_count !== null ? stats.archives_count : 'Unknown');

        // Job statistics
        $('#total-backups').text(stats.total_jobs !== null ? stats.total_jobs : 0);
        $('#successful-backups').text(stats.successful_jobs !== null ? stats.successful_jobs : 0);
        $('#failed-backups').text(stats.failed_jobs !== null ? stats.failed_jobs : 0);

        // Calculate success rate
        let successRate = 0;
        if (stats.successful_jobs !== null && stats.total_jobs !== null && stats.total_jobs > 0) {
            successRate = (stats.successful_jobs / stats.total_jobs) * 100;
            $('#success-rate').text(formatPercent(successRate));
        } else {
            $('#success-rate').text('N/A');
        }

        // Average size and compression are derived from job data
        $('#average-size').text(stats.average_size || 'Unknown');
        $('#average-compression').text(stats.average_compression || 'Unknown');

        // Last backup time
        $('#last-backup').text(stats.last_backup_time ? formatDate(stats.last_backup_time) : 'Never');
    }

    // Update forecast display
    function updateForecastDisplay(forecast) {
        if (!forecast || Object.keys(forecast).length === 0) {
            // No forecast data available
            $('#forecast-section').hide();
            return;
        }

        adjusted_growth_rate = forecast.growth_rate.toFixed(2);

        // Set the growth rate value
        if (forecast.growth_rate !== null && forecast.growth_rate !== undefined) {
            $('#growth-rate-value').text(adjusted_growth_rate + ' GB/month');
        } else {
            $('#growth-rate-value').text('Unknown');
        }

        // Set the full date value
        if (forecast.max_date) {
            full_date = new Date(forecast.max_date);
            full_date = full_date.toLocaleDateString(navigator.language);

            $('#full-date-value').text(full_date);

            // Add days until full
            if (forecast.days_until_max) {
                $('#full-date-note').text(`${forecast.days_until_max} days until full based on current growth rate`);
            }
        } else {
            $('#full-date-value').text('Unknown');
            $('#full-date-note').text('Not enough data to estimate');
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
            success: function (stats) {
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

                    // Load data for growth chart
                    loadGrowthChart();

                    // Load backup frequency chart
                    loadFrequencyChart();

                    // Load success rate chart
                    loadSuccessRateChart();

                    // Load forecast data
                    loadForecastData();

                    $('#analytics-loading').addClass('d-none');
                    $('#analytics-content').removeClass('d-none');
                } catch (e) {
                    console.error("Error processing stats:", e);
                    $('#analytics-loading').addClass('d-none');
                    $('#analytics-content').html(
                        '<div class="alert alert-warning">' +
                        '<i class="fas fa-exclamation-triangle me-2"></i>' +
                        'Error processing repository statistics: ' + e.message +
                        '</div>'
                    ).removeClass('d-none');
                }
            },
            error: function (xhr, status, error) {
                console.error("Error loading stats:", error);
                $('#analytics-loading').addClass('d-none');
                $('#analytics-content').html(
                    '<div class="alert alert-danger">' +
                    '<i class="fas fa-exclamation-circle me-2"></i>' +
                    'Error loading repository statistics: ' + error +
                    '</div>'
                ).removeClass('d-none');
            }
        });
    }

    // Load forecast data
    function loadForecastData() {
        $.ajax({
            url: repoForecastApiUrl,
            type: 'GET',
            dataType: 'json',
            success: function (forecast) {
                console.log("Forecast data loaded:", forecast);

                if (!forecast.forecast_available) {
                    $('#forecast-section').html(
                        '<div class="alert alert-info">' +
                        '<i class="fas fa-info-circle me-2"></i>' +
                        (forecast.message || 'Not enough data available for forecasting.') +
                        '</div>'
                    );
                    return;
                }

                // Update forecast display
                updateForecastDisplay(forecast);
            },
            error: function (xhr, status, error) {
                console.error("Error loading forecast:", error);
                $('#forecast-section').html(
                    '<div class="alert alert-danger">' +
                    '<i class="fas fa-exclamation-circle me-2"></i>' +
                    'Error loading forecast data: ' + error +
                    '</div>'
                );
            }
        });
    }

    // Load the growth chart data
    function loadGrowthChart() {
        $.ajax({
            url: repoGrowthChartUrl,
            type: 'GET',
            dataType: 'json',
            success: function (chartData) {
                console.log("Growth chart data loaded:", chartData);

                // Check if we have real data or sample data
                if (chartData.is_sample_data) {
                    // Display sample data with a note
                    $('#growth-chart-container').prepend(
                        '<div class="alert alert-info mb-3">' +
                        '<i class="fas fa-info-circle me-2"></i>' +
                        (chartData.message || 'Showing sample data. Create more backups to see actual growth.') +
                        '</div>'
                    );
                }

                // Create the chart
                const ctx = document.getElementById('growth-chart').getContext('2d');
                if (chartData.growth_data) {
                    // Get the data from the response
                    const labels = chartData.growth_data.labels || [];
                    const data = chartData.growth_data.data || [];
                    const tooltips = chartData.growth_data.archive_names || [];

                    // Create the chart
                    const growthChart = new Chart(ctx, {
                        type: 'line',
                        data: {
                            labels: labels,
                            datasets: [{
                                label: 'Repository Size (GB)',
                                data: data,
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
                                        title: function (tooltipItem) {
                                            return labels[tooltipItem[0].dataIndex];
                                        },
                                        label: function (tooltipItem) {
                                            const dataIndex = tooltipItem.dataIndex;
                                            const sizeValue = data[dataIndex];
                                            const archiveName = tooltips[dataIndex] || 'Unknown';

                                            return [
                                                `Archive: ${archiveName}`,
                                                `Size: ${sizeValue.toFixed(2)} GB`
                                            ];
                                        }
                                    }
                                }
                            }
                        }
                    });
                } else {
                    // Fallback if we don't have the expected data format
                    $('#growth-chart-container').html(
                        '<div class="alert alert-warning">' +
                        '<i class="fas fa-exclamation-triangle me-2"></i>' +
                        'Unable to display growth chart: data format not recognized.' +
                        '</div>'
                    );
                }
            },
            error: function (xhr, status, error) {
                console.error("Error loading growth chart:", error);
                $('#growth-chart-container').html(
                    '<div class="alert alert-danger">' +
                    '<i class="fas fa-exclamation-circle me-2"></i>' +
                    'Error loading growth chart: ' + error +
                    '</div>'
                );
            }
        });
    }

    // Load the frequency chart data
    function loadFrequencyChart() {
        $.ajax({
            url: repoFrequencyChartUrl,
            type: 'GET',
            dataType: 'json',
            success: function (chartData) {
                console.log("Frequency chart data loaded:", chartData);

                // Check if we have real data or sample data
                if (chartData.is_sample_data) {
                    // Display sample data with a note
                    $('#frequency-chart-container').prepend(
                        '<div class="alert alert-info mb-3">' +
                        '<i class="fas fa-info-circle me-2"></i>' +
                        'Showing sample data. Create more backups to see actual frequency patterns.' +
                        '</div>'
                    );
                }

                // Create charts if we have frequency data
                if (chartData.frequency_data) {
                    const dayData = chartData.frequency_data.by_day || {};

                    // First clear any existing charts to prevent duplication
                    $('#day-frequency-chart-wrapper').html('<canvas id="day-frequency-chart" style="max-height: 300px;"></canvas>');

                    // Create day of week chart
                    if (dayData.labels && dayData.data) {
                        const dayCtx = document.getElementById('day-frequency-chart').getContext('2d');
                        const dayChart = new Chart(dayCtx, {
                            type: 'bar',
                            data: {
                                labels: dayData.labels,
                                datasets: [{
                                    label: 'Backups by Day of Week',
                                    data: dayData.data,
                                    backgroundColor: 'rgba(75, 192, 192, 0.2)',
                                    borderColor: 'rgba(75, 192, 192, 1)',
                                    borderWidth: 1
                                }]
                            },
                            options: {
                                responsive: true,
                                maintainAspectRatio: true,
                                scales: {
                                    y: {
                                        beginAtZero: true,
                                        title: {
                                            display: true,
                                            text: 'Number of Backups'
                                        },
                                        ticks: {
                                            stepSize: 1
                                        }
                                    }
                                }
                            }
                        });
                    }

                } else {
                    // Fallback if we don't have the expected data format
                    $('#frequency-chart-container').html(
                        '<div class="alert alert-warning">' +
                        '<i class="fas fa-exclamation-triangle me-2"></i>' +
                        'Unable to display frequency charts: data format not recognized.' +
                        '</div>'
                    );
                }
            },
            error: function (xhr, status, error) {
                console.error("Error loading frequency chart:", error);
                $('#frequency-chart-container').html(
                    '<div class="alert alert-danger">' +
                    '<i class="fas fa-exclamation-circle me-2"></i>' +
                    'Error loading frequency chart: ' + error +
                    '</div>'
                );
            }
        });
    }

    // Load the success rate chart
    function loadSuccessRateChart() {
        // Use the stats data we already have instead of making a new API call
        // The stats should have total_jobs and successful_jobs
        $.ajax({
            url: repoStatsApiUrl,
            type: 'GET',
            dataType: 'json',
            success: function (stats) {
                console.log("Success rate chart data loaded:", stats);

                // Get the success vs failure data
                const successfulJobs = stats.successful_jobs || 0;
                const failedJobs = stats.failed_jobs || 0;
                const totalJobs = stats.total_jobs || 0;

                // Only show chart if we have jobs
                if (totalJobs > 0) {
                    // Hide the no-data message
                    $('#success-chart-no-data').addClass('d-none');

                    // Create the chart
                    const ctx = document.getElementById('success-rate-chart').getContext('2d');
                    const successChart = new Chart(ctx, {
                        type: 'pie',
                        data: {
                            labels: ['Successful', 'Failed'],
                            datasets: [{
                                data: [successfulJobs, failedJobs],
                                backgroundColor: [
                                    'rgba(75, 192, 192, 0.6)',
                                    'rgba(255, 99, 132, 0.6)'
                                ],
                                borderColor: [
                                    'rgba(75, 192, 192, 1)',
                                    'rgba(255, 99, 132, 1)'
                                ],
                                borderWidth: 1
                            }]
                        },
                        options: {
                            responsive: true,
                            maintainAspectRatio: true,
                            plugins: {
                                legend: {
                                    position: 'bottom'
                                },
                                tooltip: {
                                    callbacks: {
                                        label: function (tooltipItem) {
                                            const dataset = tooltipItem.dataset;
                                            const total = dataset.data.reduce((acc, data) => acc + data, 0);
                                            const currentValue = dataset.data[tooltipItem.dataIndex];
                                            const percentage = ((currentValue / total) * 100).toFixed(1);
                                            return `${tooltipItem.label}: ${currentValue} (${percentage}%)`;
                                        }
                                    }
                                }
                            }
                        }
                    });
                } else {
                    // Show the no-data message
                    $('#success-chart-no-data').removeClass('d-none');
                }
            },
            error: function (xhr, status, error) {
                console.error("Error loading success rate chart:", error);
                $('#success-chart-container').html(
                    '<div class="alert alert-danger">' +
                    '<i class="fas fa-exclamation-circle me-2"></i>' +
                    'Error loading success rate chart: ' + error +
                    '</div>'
                );
            }
        });
    }

    // Load analytics when the page loads
    loadAnalytics();

    // Add event handlers for interactive elements
    $('#update-max-size-button').on('click', function () {
        const maxSizeInput = $('#max-size-input').val();
        if (!maxSizeInput) {
            alert('Please enter a maximum size value.');
            return;
        }

        // Convert to number and validate
        const maxSize = parseFloat(maxSizeInput);
        if (isNaN(maxSize) || maxSize <= 0) {
            alert('Please enter a valid number greater than 0.');
            return;
        }

        // Send update request
        $.ajax({
            url: updateRepoApiUrl,
            type: 'POST',
            data: {
                max_size: maxSize
            },
            success: function (response) {
                if (response.success) {
                    alert('Maximum size updated successfully.');
                    // Reload analytics to reflect the change
                    loadAnalytics();
                } else {
                    alert('Error updating maximum size: ' + (response.error || 'Unknown error'));
                }
            },
            error: function (xhr, status, error) {
                alert('Error updating maximum size: ' + error);
            }
        });
    });

    // Set up refresh button
    $('#refresh-analytics-button').on('click', function () {
        loadAnalytics();
    });
});
