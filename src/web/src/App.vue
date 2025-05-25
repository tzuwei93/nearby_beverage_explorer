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
          Time Travel Queries</a>, Google Map API, AWS Lambda, Step Functions, S3, Vue.js, Hyparquet.js
      </p>
      <p>Data last loaded: {{ formatDate(dataLoadedAt) }}</p>
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
      <table>
        <thead>
          <tr>
            <th @click="sort('name')">Name</th>
            <!-- <th @click="sort('types')">Types</th> -->
            <th @click="sort('this_week_rating')">This Week Rating</th>
            <th @click="sort('last_week_rating')">Last Week Rating</th>
            <th @click="sort('rating_difference')">Rating Difference</th>
            <th @click="sort('rating_progression')">Rating Progression</th>
            <!-- <th @click="sort('updated_at')">Updated At</th> -->
          </tr>
        </thead>
        <tbody>
          <tr v-for="place in filteredPlaces" :key="place.place_id">
            <td><a :href="place.url" target="_blank">{{ place.name }}</a></td>
            <!-- <td>{{ formatTypes(place.types) }}</td> -->
            <td>
              {{ place.this_week_rating ? place.this_week_rating.toFixed(1) : 'N/A' }}
              <div class="stars-container" v-if="place.this_week_rating">
                <div class="stars-filled" :style="{ width: calculateStarPercentage(place.this_week_rating) + '%' }">★★★★★</div>
                <div class="stars-empty">★★★★★</div>
              </div>
            </td>
            <td>
              {{ place.last_week_rating ? place.last_week_rating.toFixed(1) : 'N/A' }}
              <div class="stars-container" v-if="place.last_week_rating">
                <div class="stars-filled" :style="{ width: calculateStarPercentage(place.last_week_rating) + '%' }">★★★★★</div>
                <div class="stars-empty">★★★★★</div>
              </div>
            </td>
            <td :class="place.rating_difference ? getRatingChangeClass(place.rating_difference) : ''">
              {{ formatRatingChange(place.rating_difference) }}
            </td>
            <td>
              <div class="progression-chart" v-if="place.rating_progression && Array.isArray(place.rating_progression)">
                <!-- Visualization of rating progression -->
                <div v-for="(rating, index) in place.rating_progression" 
                     :key="index"
                     :style="{ height: calculateProgressionHeight(rating) + '%' }"
                     class="progression-bar">
                </div>
              </div>
              <span v-else>No data</span>
            </td>
            <!-- <td>{{ formatDate(place.updated_at) }}</td> -->
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted } from 'vue'

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
    const sortKey = ref('name')
    const sortOrder = ref('asc')
    const dataLoadedAt = ref(null)
    
    // Default locations
    const defaultLocations = [
      { latitude: 25.041171, longitude: 121.565227, name: '市政府捷運站' } // City Hall MRT Station
    ]
    
    // Access environment variables (works with both Vite and Vue CLI)
    const envVars = import.meta.env || {}
    
    // Initialize locations from environment variables or use defaults
    let initialLocations = defaultLocations
    try {
      console.log('Environment variables:', envVars)
      if (envVars.VITE_LOCATIONS) {
        const parsedLocations = JSON.parse(envVars.VITE_LOCATIONS)
        if (Array.isArray(parsedLocations) && parsedLocations.length > 0) {
          initialLocations = parsedLocations
          console.log('Loaded locations from environment variables:', initialLocations)
        }
      }
    } catch (e) {
      console.error('Error parsing VITE_LOCATIONS:', e)
    }
    
    // Get AWS region from environment variables or use default
    const defaultRegion = 'ap-southeast-1'
    const awsRegion = envVars.VITE_AWS_REGION || defaultRegion
    // console.log('Using AWS region:', awsRegion)
    
    // Location management
    const locations = ref(initialLocations)
    const selectedLocationIndex = ref(parseInt(localStorage.getItem('selectedLocationIndex') || '0'))
    
    // Ensure the selected index is valid
    if (selectedLocationIndex.value >= locations.value.length) {
      selectedLocationIndex.value = 0
      localStorage.setItem('selectedLocationIndex', '0')
    }
    
    // Handle location change
    const handleLocationChange = () => {
      // Save selected location to localStorage
      localStorage.setItem('selectedLocationIndex', selectedLocationIndex.value.toString())
      // Reload data with new location
      loadData()
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
        
        const bucketUrl = `https://nearby-beverage-explorer-data.s3.${awsRegion}.amazonaws.com`
        
        // Get the current selected location
        const currentLocation = locations.value[selectedLocationIndex.value]
        const { latitude, longitude, name } = currentLocation
        console.log(`Using location: ${name || ''} (${latitude}, ${longitude})`)
        
        // Create prefix with location information
        const prefix = `analytics/${latitude}_${longitude}/beverage_establishments/`
        
        // Get the parquet file from the bucket
        const fileKey = await getParquetFile(bucketUrl, prefix)
        console.log('Found parquet file:', fileKey)
        
        // Load the parquet file using Hyparquet
        const { asyncBufferFromUrl, parquetReadObjects } = await import('hyparquet')
        const url = `${bucketUrl}/${fileKey}`
        const file = await asyncBufferFromUrl({ url })
        
        // Read the parquet file
        const data = await parquetReadObjects({
          file,
          columns: ['place_id', 'name', 'types', 'url', 'this_week_rating', 'last_week_rating', 'rating_progression', 'rating_difference', 'updated_at']
        })
        
        places.value = data
        dataLoadedAt.value = places.value[0].updated_at
        console.log('Loaded data:', data)
      } catch (err) {
        error.value = 'Failed to load data. Please try again later.'
        console.error('Error loading data:', err)
      } finally {
        loading.value = false
      }
    }

    const filteredPlaces = computed(() => {
      return places.value
        .filter(place => {
          // Add null checks for all properties
          if (!place || !place.name) return false;
          
          const matchesSearch = place.name.toLowerCase().includes(searchQuery.value.toLowerCase())
          const matchesRating = !ratingFilter.value || (place.this_week_rating && place.this_week_rating >= parseFloat(ratingFilter.value))
          // const matchesType = !typeFilter.value || (place.types && place.types.includes(typeFilter.value))
          return matchesSearch && matchesRating
        })
        .sort((a, b) => {
          const aVal = a[sortKey.value]
          const bVal = b[sortKey.value]
          const modifier = sortOrder.value === 'asc' ? 1 : -1
          return aVal > bVal ? modifier : -modifier
        })
    })

    const sort = (key) => {
      if (sortKey.value === key) {
        sortOrder.value = sortOrder.value === 'asc' ? 'desc' : 'asc'
      } else {
        sortKey.value = key
        sortOrder.value = 'asc'
      }
    }

    const formatDate = (timestamp) => {
      if (!timestamp) return 'N/A';
      try {
        return new Date(timestamp).toLocaleDateString();
      } catch (e) {
        return 'Invalid date';
      }
    }

    const formatRatingChange = (change) => {
      if (change === undefined || change === null) return '-'
      return change > 0 ? `+${change.toFixed(1)}` : change.toFixed(1)
    }

    const getRatingChangeClass = (change) => {
      if (change === undefined || change === null) return ''
      return change > 0 ? 'positive-change' : 'negative-change'
    }
    
    const calculateProgressionHeight = (rating) => {
      if (rating === undefined || rating === null) return 0
      // Scale the rating to a percentage (assuming ratings are between 0-5)
      return Math.min(Math.max(rating * 20, 0), 100)
    }
    
    const calculateStarPercentage = (rating) => {
      if (rating === undefined || rating === null) return 0
      // Convert rating (0-5) to percentage (0-100)
      return Math.min(Math.max(rating * 20, 0), 100)
    }
    
    const formatTypes = (types) => {
      if (!types) return 'N/A'
      
      // Check if types is already a string
      if (typeof types === 'string') {
        try {
          // Try to parse it in case it's a JSON string
          const parsedTypes = JSON.parse(types)
          if (Array.isArray(parsedTypes)) {
            return parsedTypes
              .map(type => type.charAt(0).toUpperCase() + type.slice(1).replace('_', ' '))
              .join(', ')
          }
          return types
        } catch (e) {
          // If it's not valid JSON, return as is
          return types
        }
      }
      
      // If types is an array
      if (Array.isArray(types)) {
        return types
          .map(type => type.charAt(0).toUpperCase() + type.slice(1).replace('_', ' '))
          .join(', ')
      }
      
      // If it's neither a string nor an array, return as string
      return String(types)
    }

    const exportToCsv = () => {
      const headers = ['Name', 'URL', 'This Week Rating', 'Last Week Rating', 'Rating Difference', 'Rating Progression', 'Updated At']
      const csvContent = [
        headers.join(','),
        ...filteredPlaces.value.map(place => [
          place.name,
          place.url,
          place.this_week_rating || '',
          place.last_week_rating || '',
          place.rating_difference || '',
          place.rating_progression ? JSON.stringify(place.rating_progression) : '',
          place.updated_at || ''
        ].join(','))
      ].join('\n')

      const blob = new Blob([csvContent], { type: 'text/csv' })
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `nearby-beverage-explorer-ratings-${new Date().toISOString().split('T')[0]}.csv`
      a.click()
      window.URL.revokeObjectURL(url)
    }

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
      calculateProgressionHeight,
      calculateStarPercentage,
      formatTypes,
      exportToCsv,
      dataLoadedAt,
      // Location-related variables
      locations,
      selectedLocationIndex,
      handleLocationChange
    }
  }
}
</script>

<style>
.container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px;
}

header {
  text-align: center;
  margin-bottom: 30px;
}

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
}

.filters {
  display: flex;
  gap: 15px;
  margin-bottom: 20px;
}

.search-input,
.type-filter,
.rating-filter {
  padding: 8px;
  border: 1px solid #ddd;
  border-radius: 4px;
}

.export-btn {
  padding: 8px 16px;
  background-color: #4CAF50;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}

.table-container {
  overflow-x: auto;
}

table {
  width: 100%;
  border-collapse: collapse;
  margin-top: 20px;
}

th, td {
  padding: 12px;
  text-align: left;
  border-bottom: 1px solid #ddd;
}

th {
  background-color: #f5f5f5;
  cursor: pointer;
}

.stars-container {
  position: relative;
  display: inline-block;
  margin-left: 5px;
  white-space: nowrap;
  line-height: 1;
}

.stars-filled {
  position: absolute;
  top: 0;
  left: 0;
  overflow: hidden;
  color: #FFD700;
  z-index: 1;
}

.stars-empty {
  color: #e0e0e0;
}

.positive-change {
  color: #4CAF50;
}

.negative-change {
  color: #f44336;
}

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

.popular-times {
  display: flex;
  gap: 2px;
  height: 30px;
  align-items: flex-end;
}

.progression-chart {
  display: flex;
  gap: 2px;
  height: 30px;
  align-items: flex-end;
  width: 100%;
}

.progression-bar {
  flex: 1;
  background-color: #4CAF50;
  min-height: 2px;
  border-radius: 1px 1px 0 0;
  transition: height 0.3s ease;
}

.hour-bar {
  width: 4px;
  background-color: #2196F3;
  min-height: 1px;
}

.maps-link {
  color: #2196F3;
  text-decoration: none;
}

.maps-link:hover {
  text-decoration: underline;
}

.loading {
  text-align: center;
  padding: 40px;
  font-size: 1.2em;
  color: #666;
}

.error {
  text-align: center;
  padding: 40px;
  color: #f44336;
}
</style> 