// Location management utilities
// Handles location selection, storage, and environment configuration

export const locationService = {
  /**
   * Default locations for the application
   */
  defaultLocations: [
    { latitude: 25.041171, longitude: 121.565227, name: '市政府捷運站' } // City Hall MRT Station
  ],

  /**
   * Initialize locations from environment variables or use defaults
   * @param {Object} envVars - Environment variables object
   * @returns {Array} - Array of location objects
   */
  initializeLocations(envVars) {
    let initialLocations = this.defaultLocations
    
    try {
      console.log('Environment variables:', envVars)
      if (envVars.VITE_LOCATIONS) {
        const parsedLocations = JSON.parse(envVars.VITE_LOCATIONS)
        if (Array.isArray(parsedLocations) && parsedLocations.length > 0) {
          initialLocations = parsedLocations
          console.log('Using locations from environment:', initialLocations)
        }
      }
    } catch (e) {
      console.error('Error parsing VITE_LOCATIONS:', e)
    }
    
    return initialLocations
  },

  /**
   * Get AWS configuration from environment variables
   * @param {Object} envVars - Environment variables object
   * @returns {Object} - AWS configuration object
   */
  getAwsConfig(envVars) {
    const defaultRegion = 'ap-southeast-1'
    const defaultBucketName = 'nearby-beverage-explorer-data'
    
    return {
      awsRegion: envVars.VITE_AWS_REGION || defaultRegion,
      s3BucketName: envVars.VITE_S3_BUCKET_NAME || defaultBucketName
    }
  },

  /**
   * Get selected location index from localStorage
   * @param {number} maxIndex - Maximum valid index
   * @returns {number} - Valid selected location index
   */
  getSelectedLocationIndex(maxIndex) {
    let selectedIndex = parseInt(localStorage.getItem('selectedLocationIndex') || '0')
    
    // Ensure the selected index is valid
    if (selectedIndex >= maxIndex) {
      selectedIndex = 0
      this.saveSelectedLocationIndex(selectedIndex)
    }
    
    return selectedIndex
  },

  /**
   * Save selected location index to localStorage
   * @param {number} index - Location index to save
   */
  saveSelectedLocationIndex(index) {
    localStorage.setItem('selectedLocationIndex', index.toString())
  },

  /**
   * Handle location change event
   * @param {number} newIndex - New location index
   * @param {Function} callback - Callback function to execute after saving
   */
  handleLocationChange(newIndex, callback) {
    this.saveSelectedLocationIndex(newIndex)
    if (typeof callback === 'function') {
      callback()
    }
  },

  /**
   * Get current location object
   * @param {Array} locations - Array of locations
   * @param {number} selectedIndex - Selected location index
   * @returns {Object} - Current location object
   */
  getCurrentLocation(locations, selectedIndex) {
    if (!locations || locations.length === 0) {
      return this.defaultLocations[0]
    }
    
    if (selectedIndex >= 0 && selectedIndex < locations.length) {
      return locations[selectedIndex]
    }
    
    return locations[0]
  }
}
