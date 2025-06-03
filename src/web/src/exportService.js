// Export utilities
// Handles data export functionality (CSV, etc.)

import { dateUtils, dataUtils } from './utils.js'

export const exportService = {
  /**
   * Export filtered places data to CSV format
   * @param {Array} filteredPlaces - Array of filtered place objects
   * @param {string} filename - Optional filename (without extension)
   * @returns {void}
   */
  exportToCsv(filteredPlaces, filename = null) {
    const headers = ['Name', 'URL', 'Current Rating', 'Latest Change', 'Change Period', 'Rating History', 'Latitude', 'Longitude']
    
    // Generate CSV content
    const csvContent = [
      headers.join(','),
      ...filteredPlaces.map(place => [
        `"${place.name}"`,
        `"${place.url}"`,
        place.current_rating ? place.current_rating.toFixed(1) : '',
        place.latest_change_value ? place.latest_change_value.toFixed(1) : '',
        `"${place.latest_change_period || ''}"`,
        `"${dataUtils.formatHistoryRatingsForCsv(place.history_ratings)}"`,
        place.latitude ? place.latitude.toFixed(4) : '',
        place.longitude ? place.longitude.toFixed(4) : ''
      ].join(','))
    ].join('\n')

    // Generate filename if not provided
    const finalFilename = filename || `nearby-beverage-explorer-ratings-${new Date().toISOString().split('T')[0]}`
    
    // Download the CSV file
    this.downloadFile(csvContent, `${finalFilename}.csv`, 'text/csv')
  },

  /**
   * Export filtered places data to JSON format
   * @param {Array} filteredPlaces - Array of filtered place objects
   * @param {string} filename - Optional filename (without extension)
   * @returns {void}
   */
  exportToJson(filteredPlaces, filename = null) {
    const jsonContent = JSON.stringify(filteredPlaces, null, 2)
    
    // Generate filename if not provided
    const finalFilename = filename || `nearby-beverage-explorer-data-${new Date().toISOString().split('T')[0]}`
    
    // Download the JSON file
    this.downloadFile(jsonContent, `${finalFilename}.json`, 'application/json')
  },

  /**
   * Generate summary statistics for export
   * @param {Array} places - Array of place objects
   * @returns {Object} - Summary statistics object
   */
  generateSummaryStats(places) {
    const validRatings = places
      .map(place => place.current_rating)
      .filter(rating => rating !== null && rating !== undefined)
    
    if (validRatings.length === 0) {
      return {
        totalPlaces: places.length,
        placesWithRatings: 0,
        averageRating: null,
        minRating: null,
        maxRating: null
      }
    }
    
    const sum = validRatings.reduce((acc, rating) => acc + rating, 0)
    const average = sum / validRatings.length
    
    return {
      totalPlaces: places.length,
      placesWithRatings: validRatings.length,
      averageRating: parseFloat(average.toFixed(2)),
      minRating: Math.min(...validRatings),
      maxRating: Math.max(...validRatings)
    }
  },

  /**
   * Export summary report
   * @param {Array} places - Array of place objects
   * @param {Object} metadata - Additional metadata
   * @param {string} filename - Optional filename (without extension)
   * @returns {void}
   */
  exportSummaryReport(places, metadata = {}, filename = null) {
    const stats = this.generateSummaryStats(places)
    const report = {
      generatedAt: new Date().toISOString(),
      location: metadata.location || 'Unknown',
      dataSource: metadata.fileKey || 'Unknown',
      summary: stats,
      places: places
    }
    
    const finalFilename = filename || `beverage-explorer-report-${new Date().toISOString().split('T')[0]}`
    this.exportToJson(report, finalFilename)
  },

  /**
   * Download file helper
   * @param {string} content - File content
   * @param {string} filename - Filename with extension
   * @param {string} mimeType - MIME type
   * @returns {void}
   */
  downloadFile(content, filename, mimeType) {
    const blob = new Blob([content], { type: mimeType })
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    a.click()
    window.URL.revokeObjectURL(url)
  },

  /**
   * Get export formats configuration
   * @returns {Array} - Available export formats
   */
  getExportFormats() {
    return [
      {
        key: 'csv',
        label: 'CSV (Excel)',
        description: 'Comma-separated values for Excel',
        handler: this.exportToCsv.bind(this)
      },
      {
        key: 'json',
        label: 'JSON (Data)',
        description: 'Raw JSON data format',
        handler: this.exportToJson.bind(this)
      },
      {
        key: 'report',
        label: 'Summary Report',
        description: 'Complete report with statistics',
        handler: this.exportSummaryReport.bind(this)
      }
    ]
  }
}
