// Data loading and API service utilities
// Handles S3 operations, parquet file loading, and data processing

import { ratingUtils, dateUtils, safeJsonParse } from './utils.js'

export const dataService = {
  /**
   * Find the latest parquet file in the specified S3 bucket path
   * @param {string} bucketUrl - Base S3 bucket URL
   * @param {string} prefix - S3 prefix path
   * @returns {Promise<string>} - The key of the latest parquet file
   */
  async getLatestParquetFile(bucketUrl, prefix) {
    try {
      // Use fetch to call a public list-objects compatible endpoint
      const response = await fetch(`${bucketUrl}?list-type=2&prefix=${encodeURIComponent(prefix)}&max-keys=100`)
      if (!response.ok) {
        throw new Error(`Failed to list files: ${response.statusText}`)
      }
      
      const xmlText = await response.text()
      const parser = new DOMParser()
      const xmlDoc = parser.parseFromString(xmlText, 'text/xml')
      
      // Extract all files from the XML response
      const contents = xmlDoc.getElementsByTagName('Contents')
      if (contents.length === 0) {
        throw new Error('No files found in the bucket')
      }
      
      // Filter for only parquet files and get their keys and last modified dates
      const parquetFiles = []
      for (let i = 0; i < contents.length; i++) {
        const key = contents[i].getElementsByTagName('Key')[0].textContent
        if (key.endsWith('.parquet')) {
          const lastModified = new Date(contents[i].getElementsByTagName('LastModified')[0].textContent)
          parquetFiles.push({ key, lastModified })
        }
      }
      
      if (parquetFiles.length === 0) {
        throw new Error('No parquet files found in the bucket')
      }
      
      // Sort by last modified date (newest first)
      parquetFiles.sort((a, b) => b.lastModified - a.lastModified)
      
      // Get the latest parquet file
      const latestFile = parquetFiles[0]
      console.log('Found latest parquet file:', latestFile.key, 'Modified:', latestFile.lastModified)
      
      return latestFile.key
    } catch (error) {
      console.error('Error getting parquet file:', error)
      throw error
    }
  },

  /**
   * Load and process parquet data from S3
   * @param {string} bucketUrl - S3 bucket URL
   * @param {string} fileKey - Parquet file key
   * @returns {Promise<Array>} - Processed place data
   */
  async loadParquetData(bucketUrl, fileKey) {
    try {
      // Load the parquet file using Hyparquet
      const { asyncBufferFromUrl, parquetReadObjects } = await import('hyparquet')
      const url = `${bucketUrl}/${fileKey}`
      const file = await asyncBufferFromUrl({ url })
      
      // Read the parquet file
      const data = await parquetReadObjects({
        file,
        columns: ['unique_id', 'name', 'latitude', 'longitude', 'history_ratings', 'rating_change', 'google_maps_url']
      })
      
      return data
    } catch (error) {
      console.error('Error loading parquet data:', error)
      throw error
    }
  },

  /**
   * Process raw place data into display format
   * @param {Array} rawData - Raw parquet data
   * @returns {Array} - Processed place data with ratings and history
   */
  processPlaceData(rawData) {
    return rawData.map(place => {
      let currentRating = null
      let latestChangeValue = null
      let latestChangeDisplay = null
      let latestChangePeriod = null
      let ratingHistoryDetails = ''

      // Process ratings history data
      if (place.history_ratings) {
        try {
          const historyObj = safeJsonParse(place.history_ratings)
          const historyResult = ratingUtils.processHistory(historyObj)
          
          currentRating = historyResult.currentRating
          latestChangeValue = historyResult.latestChangeValue
          latestChangeDisplay = historyResult.latestChangeDisplay
          latestChangePeriod = historyResult.latestChangePeriod
          ratingHistoryDetails = historyResult.ratingHistoryDetails
        } catch (e) {
          console.warn('Error processing history ratings for place:', place.name, e)
        }
      }

      return {
        ...place,
        current_rating: currentRating,
        latest_change_value: latestChangeValue,
        latest_change_display: latestChangeDisplay,
        latest_change_period: latestChangePeriod,
        rating_history_details: ratingHistoryDetails,
        // Use the Google Maps URL provided by the backend
        url: place.google_maps_url
      }
    })
  },

  /**
   * Load complete dataset for a specific location
   * @param {Object} config - Configuration object
   * @param {string} config.s3BucketName - S3 bucket name
   * @param {string} config.awsRegion - AWS region
   * @param {Object} config.location - Location object with latitude, longitude, name
   * @returns {Promise<Object>} - Result object with data and metadata
   */
  async loadLocationData({ s3BucketName, awsRegion, location }) {
    try {
      const bucketUrl = `https://${s3BucketName}.s3.${awsRegion}.amazonaws.com`
      
      const { latitude, longitude, name } = location
      console.log(`Loading data for location: ${name || ''} (${latitude}, ${longitude})`)
      
      // Create prefix with location information
      const prefix = `analytics/${latitude}_${longitude}/beverage_analytics/`
      
      // Get the parquet file from the bucket
      const fileKey = await this.getLatestParquetFile(bucketUrl, prefix)
      console.log('Found parquet file:', fileKey)
      
      // Load and process the data
      const rawData = await this.loadParquetData(bucketUrl, fileKey)
      const processedData = this.processPlaceData(rawData)
      
      return {
        data: processedData,
        fileKey,
        location
      }
    } catch (error) {
      console.error('Error in loadLocationData:', error)
      throw error
    }
  }
}
