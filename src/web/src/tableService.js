// Table filtering and sorting utilities
// Handles search, filtering, and sorting operations for the data table

export const tableService = {
  /**
   * Filter places based on search query and rating filter
   * @param {Array} places - Array of place objects
   * @param {string} searchQuery - Search query string
   * @param {string} ratingFilter - Minimum rating filter
   * @returns {Array} - Filtered array of places
   */
  filterPlaces(places, searchQuery, ratingFilter) {
    return places.filter(place => {
      // Add null checks for all properties
      if (!place || !place.name) return false
      
      const matchesSearch = place.name.toLowerCase().includes(searchQuery.toLowerCase())
      const matchesRating = !ratingFilter || (place.current_rating && place.current_rating >= parseFloat(ratingFilter))
      return matchesSearch && matchesRating
    })
  },

  /**
   * Sort places by specified key and order
   * @param {Array} places - Array of place objects
   * @param {string} sortKey - Key to sort by
   * @param {string} sortOrder - Sort order ('asc' or 'desc')
   * @returns {Array} - Sorted array of places
   */
  sortPlaces(places, sortKey, sortOrder) {
    return places.sort((a, b) => {
      const aVal = a[sortKey]
      const bVal = b[sortKey]
      const modifier = sortOrder === 'asc' ? 1 : -1
      
      // Handle null values
      if (aVal === null || aVal === undefined) return 1
      if (bVal === null || bVal === undefined) return -1
      
      return aVal > bVal ? modifier : -modifier
    })
  },

  /**
   * Apply filtering and sorting to places array
   * @param {Array} places - Array of place objects
   * @param {Object} filters - Filter configuration
   * @param {string} filters.searchQuery - Search query
   * @param {string} filters.ratingFilter - Rating filter
   * @param {string} filters.sortKey - Sort key
   * @param {string} filters.sortOrder - Sort order
   * @returns {Array} - Filtered and sorted places
   */
  processPlaces(places, { searchQuery, ratingFilter, sortKey, sortOrder }) {
    let filteredPlaces = this.filterPlaces(places, searchQuery, ratingFilter)
    return this.sortPlaces(filteredPlaces, sortKey, sortOrder)
  },

  /**
   * Handle sort operation and update DOM
   * @param {string} key - Sort key
   * @param {Object} currentSort - Current sort state
   * @param {Function} updateSort - Function to update sort state
   */
  handleSort(key, currentSort, updateSort) {
    let newSortKey = key
    let newSortOrder = 'asc'
    
    if (currentSort.sortKey === key) {
      newSortOrder = currentSort.sortOrder === 'asc' ? 'desc' : 'asc'
    }
    
    // Update sort state
    updateSort(newSortKey, newSortOrder)
    
    // Add sort indicator class to the header
    setTimeout(() => {
      const headers = document.querySelectorAll('th')
      headers.forEach(header => {
        header.classList.remove('sort-asc', 'sort-desc')
        if (header.textContent.includes(key)) {
          header.classList.add(newSortOrder === 'asc' ? 'sort-asc' : 'sort-desc')
        }
      })
    }, 0)
  },

  /**
   * Get available filter options from data
   * @param {Array} places - Array of place objects
   * @returns {Object} - Available filter options
   */
  getFilterOptions(places) {
    const ratings = places
      .map(place => place.current_rating)
      .filter(rating => rating !== null && rating !== undefined)
      .sort((a, b) => a - b)
    
    const minRating = ratings.length > 0 ? Math.floor(ratings[0]) : 0
    const maxRating = ratings.length > 0 ? Math.ceil(ratings[ratings.length - 1]) : 5
    
    return {
      minRating,
      maxRating,
      ratingSteps: [minRating, minRating + 1, minRating + 2, minRating + 3, maxRating]
    }
  }
}
