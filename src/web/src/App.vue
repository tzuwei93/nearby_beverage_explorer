<template>
  <div class="container">
    <header>
      <h1>Nearby Beverage Explorer</h1>
      <div class="location-selector">
        <label for="location-select">Location:</label>
        <select id="location-select" v-model="selectedLocationIndex" @change="handleLocationChange">
          <option v-for="(location, index) in locations" :key="index" :value="index">
            {{ location.name }} ({{ location.latitude }}, {{ location.longitude }})
          </option>
        </select>
      </div>
      <p>
        Powered by Apache Hudi <a href="https://hudi.apache.org/docs/quick-start-guide/#timetravel" target="_blank" rel="noopener noreferrer">
          Time Travel Queries</a>, Google Map API, AWS Lambda, Step Functions, S3, Vue.js, <a href="https://github.com/hyparam/hyparquet" target="_blank" rel="noopener noreferrer">Hyparquet.js</a>
      </p>
    </header>

    <div class="filters">
      <input 
        v-model="searchQuery" 
        placeholder="Search by name..." 
        class="search-input"
      />
      <!-- <select v-model="typeFilter" class="type-filter">
        <option value="">All Types</option>
        <option value="cafe">Cafe</option>
      </select> -->
      <select v-model="ratingFilter" class="rating-filter">
        <option value="">All Ratings</option>
        <option value="4">4+ Stars</option>
        <option value="3">3+ Stars</option>
        <option value="2">2+ Stars</option>
      </select>
      <button @click="exportToCsv" class="export-btn">Export to CSV</button>
    </div>

    <div v-if="loading" class="loading">
      Loading data...
    </div>
    <div v-else-if="error" class="error">
      {{ error }}
    </div>
    <div v-else class="table-container">
      <div class="pagination-controls">
        <button 
          @click="currentPage--" 
          :disabled="currentPage === 1"
          class="pagination-button"
        >
          Previous
        </button>
        <span class="page-info">
          Page {{ currentPage }} of {{ totalPages }}
        </span>
        <button 
          @click="currentPage++" 
          :disabled="currentPage >= totalPages"
          class="pagination-button"
        >
          Next
        </button>
      </div>
      <table>
        <thead>
          <tr>
            <th @click="sort('name')">Name</th>
            <th @click="sort('current_rating')">Latest Rating</th>
            <th @click="sort('rating_difference_sort_value')">
              Rating Difference
              <span
                class="tooltip-header-icon"
                @mouseenter="showTooltip($event, 'Shows the difference between the highest and lowest ratings in the past 6 months. The value is calculated as (highest - lowest). And also the latest rating will be presented.')"
                @mouseleave="hideTooltip()"
              >ⓘ</span>
            </th>
            <th>Location</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="place in paginatedPlaces" :key="place.unique_id" 
              class="data-row">
            <td>
              <a :href="place.url" target="_blank" class="maps-link">{{ place.name }}</a>
            </td>
            <td>
              {{ place.current_rating ? place.current_rating.toFixed(1) : 'N/A' }}
              <div class="stars-container" v-if="place.current_rating">
                <div class="stars-filled" :style="{ width: calculateStarPercentage(place.current_rating) + '%' }">★★★★★</div>
                <div class="stars-empty">★★★★★</div>
              </div>
            </td>
            <td class="tooltip-trigger"
              @mouseenter="showTooltip($event, place.rating_history_details)"
              @mouseleave="hideTooltip()">
              <div v-if="place.rating_range_display !== null">
                {{ place.rating_range_display }}
                <br><small class="rating-range-period">{{ place.rating_range_period }}</small>
              </div>
              <div v-else>-</div>
            </td>
            <td>
              <small>{{ place.latitude.toFixed(4) }}, {{ place.longitude.toFixed(4) }}</small>
            </td>
          </tr>
        </tbody>
      </table>
      
      <!-- Footer with GitHub link -->
      <footer class="app-footer">
        <div class="footer-content">
          <p>This project is open source on 
            <a href="https://github.com/tzuwei93/nearby_beverage_explorer" 
               target="_blank" 
               rel="noopener noreferrer"
               class="github-link">
              GitHub
            </a>
          </p>
        </div>
      </footer>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted, watch } from 'vue'
import { dateUtils, ratingUtils, tooltipUtils, dataUtils } from './utils.js'
import { dataService } from './dataService.js'
import { locationService } from './locationService.js'
import { tableService } from './tableService.js'
import { exportService } from './exportService.js'

export default {
  name: 'App',
  setup() {
    // Data refs
    const places = ref([])
    const loading = ref(true)
    const error = ref(null)
    const searchQuery = ref('')
    const typeFilter = ref('')
    const ratingFilter = ref('')
    // Default sort by rating difference (absolute value) descending
    const sortKey = ref('rating_difference_sort_value')
    const sortOrder = ref('desc')
    const currentPage = ref(1)
    const itemsPerPage = 5
    
    // Access environment variables (works with both Vite and Vue CLI)
    const envVars = import.meta.env || {}
    
    // Initialize locations and AWS configuration
    const initialLocations = locationService.initializeLocations(envVars)
    const awsConfig = locationService.getAwsConfig(envVars)
    
    // Location management
    const locations = ref(initialLocations)
    const selectedLocationIndex = ref(locationService.getSelectedLocationIndex(locations.value.length))
    
    // Handle location change
    const handleLocationChange = () => {
      locationService.handleLocationChange(selectedLocationIndex.value, loadData)
    }

    const getParquetFile = async (bucketUrl, prefix) => {
      try {
        // Use fetch to call a public list-objects compatible endpoint
        // Get more files to ensure we find all parquet files
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
    }
    
    const loadData = async () => {
      try {
        loading.value = true
        error.value = null
        
        // Get the current selected location
        const currentLocation = locationService.getCurrentLocation(locations.value, selectedLocationIndex.value)
        
        // Load data using the data service
        const result = await dataService.loadLocationData({
          s3BucketName: awsConfig.s3BucketName,
          awsRegion: awsConfig.awsRegion,
          location: currentLocation
        })
        
        places.value = result.data
        console.log('Loaded data:', result.data)
      } catch (err) {
        error.value = 'Failed to load data. Please try again later.'
        console.error('Error loading data:', err)
      } finally {
        loading.value = false
      }
    }

    const filteredPlaces = computed(() => {
      return tableService.processPlaces(places.value, {
        searchQuery: searchQuery.value,
        ratingFilter: ratingFilter.value,
        sortKey: sortKey.value,
        sortOrder: sortOrder.value
      })
    })

    const totalPages = computed(() => {
      return Math.ceil(filteredPlaces.value.length / itemsPerPage)
    })

    const paginatedPlaces = computed(() => {
      const start = (currentPage.value - 1) * itemsPerPage
      const end = start + itemsPerPage
      return filteredPlaces.value.slice(start, end)
    })

    // Reset to first page when filters change
    watch([searchQuery, ratingFilter, sortKey, sortOrder], () => {
      currentPage.value = 1
    })

    const sort = (key) => {
      tableService.handleSort(key, { sortKey: sortKey.value, sortOrder: sortOrder.value }, (newSortKey, newSortOrder) => {
        sortKey.value = newSortKey
        sortOrder.value = newSortOrder
      })
    }

    const formatDate = (timestamp) => {
      if (!timestamp) return 'N/A';
      
      try {
        // Use our unified date parsing and formatting utilities
        const parsedDate = dateUtils.parseTimestamp(timestamp);
        return parsedDate.valid ? dateUtils.format(parsedDate.date) : 'Invalid date';
      } catch (e) {
        console.warn('Error formatting date:', timestamp, e);
        return 'Invalid date';
      }
    }

    // Use the shared calculation function for stars
    const calculateStarPercentage = (rating) => ratingUtils.calculatePercentage(rating)
    
    // For backwards compatibility in component references
    const getRatingChangeClass = ratingUtils.getChangeClass
    const formatRatingChange = ratingUtils.formatChange
    
    const formatTypes = (types) => {
      return dataUtils.formatTypes(types)
    }

    const exportToCsv = () => {
      exportService.exportToCsv(filteredPlaces.value)
    }

    // Use imported tooltip utilities 
    const showTooltip = tooltipUtils.show;
    const hideTooltip = tooltipUtils.hide;

    onMounted(() => {
      loadData()
    })

    return {
      places,
      loading,
      error,
      searchQuery,
      typeFilter,
      ratingFilter,
      filteredPlaces,
      sort,
      formatDate,
      formatRatingChange,
      getRatingChangeClass,
      calculateStarPercentage,
      formatTypes,
      exportToCsv,
      // Location-related variables
      locations,
      selectedLocationIndex,
      handleLocationChange,
      // Pagination
      currentPage,
      totalPages,
      // Tooltip functions
      showTooltip,
      hideTooltip,
      // Computed
      paginatedPlaces
    }
  }
}
</script>

<style>
/* ===== LAYOUT & CONTAINERS ===== */
.container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
}

/* Header styling */
header {
  text-align: center;
  margin-bottom: 30px;
}

/* Location selector */
.location-selector {
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 10px 0;
  gap: 10px;
}

.location-selector label {
  font-weight: bold;
}

.location-selector select {
  padding: 8px;
  border: 1px solid #ddd;
  border-radius: 4px;
  min-width: 300px;
  background-color: #f8f8f8;
  box-shadow: inset 0 1px 3px rgba(0,0,0,0.05);
}

/* ===== FILTERS & CONTROLS ===== */
.filters {
  display: flex;
  gap: 15px;
  margin-bottom: 20px;
}

.search-input,
.type-filter,
.rating-filter {
  padding: 8px 12px;
  border: 1px solid #ddd;
  border-radius: 4px;
  flex: 1;
  box-shadow: inset 0 1px 3px rgba(0,0,0,0.05);
}

.export-btn {
  padding: 8px 16px;
  background-color: #4CAF50;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  transition: background-color 0.2s;
}

.export-btn:hover {
  background-color: #388E3C;
}

/* ===== TABLE STYLING ===== */
.table-container {
  overflow-x: auto;
  margin: 20px 0;
}

.pagination-controls {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 16px;
  margin-bottom: 16px;
}

.pagination-button {
  padding: 6px 12px;
  background-color: #f5f5f5;
  border: 1px solid #ddd;
  border-radius: 4px;
  cursor: pointer;
  transition: background-color 0.2s;
}

.pagination-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.pagination-button:not(:disabled):hover {
  background-color: #e0e0e0;
}

.page-info {
  min-width: 100px;
  text-align: center;
  font-weight: 500;
}

table {
  width: 100%;
  border-collapse: collapse;
  margin-top: 20px;
  overflow: hidden;
}

th, td {
  padding: 14px;
  text-align: left;
  border-bottom: 1px solid #eee;
}

th {
  background-color: #f8f9fa;
  cursor: pointer;
  font-weight: 600;
  position: relative;
  transition: background-color 0.2s;
  color: #444;
}

th:hover {
  background-color: #f0f0f0;
}

/* Sort indicators */
th::after {
  content: '';
  display: inline-block;
  width: 0;
  height: 0;
  margin-left: 8px;
  vertical-align: middle;
}

th.sort-asc::after {
  border-left: 4px solid transparent;
  border-right: 4px solid transparent;
  border-bottom: 4px solid #666;
}

th.sort-desc::after {
  border-left: 4px solid transparent;
  border-right: 4px solid transparent;
  border-top: 4px solid #666;
}

/* ===== RATING VISUALIZATION ===== */
/* Star rating display */
.stars-container {
  position: relative;
  display: inline-block;
  margin-left: 8px;
  white-space: nowrap;
  line-height: 1;
  font-size: 1.2em;
}

.stars-filled {
  position: absolute;
  top: 0;
  left: 0;
  overflow: hidden;
  color: #FFD700;
  z-index: 1;
  text-shadow: 0 1px 1px rgba(0,0,0,0.1);
}

.stars-empty {
  color: #e0e0e0;
}

/* Rating change indicators */
.positive-change {
  color: #4CAF50;
  font-weight: bold;
}

.negative-change {
  color: #f44336;
  font-weight: bold;
}

.latest-change-period {
  color: #777;
  font-size: 0.85em;
  margin-top: 5px;
  font-style: italic;
  display: inline-block;
  background-color: rgba(0, 0, 0, 0.03);
  padding: 3px 6px;
  border-radius: 4px;
  border: 1px solid rgba(0, 0, 0, 0.05);
}

/* Status indicators */
.status {
  padding: 4px 8px;
  border-radius: 12px;
  font-size: 0.9em;
}

.status.open {
  background-color: #E8F5E9;
  color: #2E7D32;
}

.status.closed {
  background-color: #FFEBEE;
  color: #C62828;
}

/* ===== CHARTS & VISUALIZATIONS ===== */

.popular-times {
  display: flex;
  gap: 2px;
  height: 30px;
  align-items: flex-end;
}

.hour-bar {
  width: 4px;
  background-color: #2196F3;
  min-height: 1px;
}

/* ===== LINKS & INTERACTIONS ===== */
.maps-link {
  color: #2196F3;
  text-decoration: none;
  font-weight: 500;
  display: inline-block;
  position: relative;
  transition: color 0.2s;
  padding-bottom: 2px;
}

.maps-link:hover {
  color: #0d47a1;
}

.maps-link:after {
  content: '';
  position: absolute;
  width: 0;
  height: 2px;
  bottom: 0;
  left: 0;
  background-color: #2196F3;
  transition: width 0.2s;
}

.maps-link:hover:after {
  width: 100%;
}

/* ===== STATE INDICATORS ===== */
.loading {
  text-align: center;
  padding: 40px;
  font-size: 1.2em;
  color: #666;
  background-color: #f9f9f9;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.05);
}

.error {
  text-align: center;
  padding: 40px;
  color: #f44336;
  background-color: #ffebee;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.05);
}

/* ===== TOOLTIP STYLING ===== */
.rating-tooltip {
  position: absolute;
  background-color: #333;
  color: white;
  padding: 15px;
  border-radius: 8px;
  font-size: 0.9em;
  line-height: 1.8;
  max-width: 350px;
  box-shadow: 0 3px 15px rgba(0,0,0,0.3);
  z-index: 1000;
  pointer-events: none;
  animation: tooltip-fade-in 0.2s ease-out;
}

.rating-tooltip::before {
  content: '';
  position: absolute;
  top: -8px;
  left: 20px;
  width: 0;
  height: 0;
  border-left: 8px solid transparent;
  border-right: 8px solid transparent;
  border-bottom: 8px solid #333;
}

/* Tooltip content structure */
.tooltip-title,
.tooltip-subtitle {
  text-align: center;
  padding-bottom: 8px;
  margin-bottom: 10px;
}

.tooltip-title {
  font-weight: bold;
  font-size: 1.1em;
  border-bottom: 1px solid rgba(255, 255, 255, 0.2);
  color: #fff;
}

.tooltip-subtitle {
  font-size: 0.9em;
  color: #cccccc;
  font-style: italic;
  border-bottom: 1px dotted rgba(255, 255, 255, 0.1);
}

.tooltip-content {
  margin-top: 10px;
}

.tooltip-date {
  font-weight: 500;
  color: #f0f0f0;
  display: inline-block;
  min-width: 140px;
  background-color: rgba(255, 255, 255, 0.1);
  padding: 2px 6px;
  border-radius: 3px;
}

.tooltip-rating {
  font-weight: bold;
  padding: 2px 6px;
  border-radius: 3px;
  min-width: 40px;
  display: inline-block;
  text-align: center;
}

/* Rating color classes */
.excellent-rating { background-color: #4CAF50; color: white; }
.good-rating { background-color: #8BC34A; color: white; }
.average-rating { background-color: #FFC107; color: #333; }
.poor-rating { background-color: #F44336; color: white; }

/* Tooltip triggers and indicators */
.tooltip-header-icon {
  font-size: 0.8em;
  color: #4a89dc;
  cursor: default;
  margin-left: 5px;
  opacity: 0.8;
  background-color: rgba(74, 137, 220, 0.1);
  padding: 2px 6px;
  border-radius: 50%;
  border: 1px solid rgba(74, 137, 220, 0.2);
}

.tooltip-trigger {
  cursor: default;
  position: relative;
}

.tooltip-trigger:hover {
  background-color: rgba(0, 0, 0, 0.03);
}

.tooltip-trigger::after {
  content: "ⓘ";
  font-size: 0.7em;
  opacity: 0.6;
  margin-left: 4px;
  vertical-align: super;
}

/* ===== ROW INTERACTIONS ===== */
.data-row {
  transition: background-color 0.2s ease;
}

.data-row:hover {
  background-color: #f5f9ff;
}

/* ===== FOOTER ===== */
.app-footer {
  margin-top: 3rem;
  padding: 1.5rem 0;
  border-top: 1px solid #e0e0e0;
  text-align: center;
  color: #666;
  font-size: 0.9rem;
}

.footer-content {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 1rem;
}

.github-link {
  color: #1976d2;
  text-decoration: none;
  font-weight: 500;
  transition: color 0.2s ease;
}

.github-link:hover {
  color: #0d47a1;
  text-decoration: underline;
}
</style>
