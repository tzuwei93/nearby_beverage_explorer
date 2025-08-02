// This file contains utility functions for date formatting, rating processing, and UI components
// These are extracted from the main application to improve code organization and reusability

// ===== Date Utils =====
export const dateUtils = {
  // Parse various timestamp formats into standardized date object
  // Assumes specific formats (17, 14, 8-digit) and ISO-like strings without timezone represent UTC+8 wall time.
  parseTimestamp: (ts) => {
    if (!ts) return { valid: false, original: ts };
    
    try {
      let date = null;
      let year, month, day, hour, minute, second, millisecond;

      // Handle YYYYMMDDHHMMSSsss format (17 digits with milliseconds) - interpret as UTC+8
      if (ts.length === 17 && /^\d+$/.test(ts)) {
        year = parseInt(ts.substr(0, 4), 10);
        month = parseInt(ts.substr(4, 2), 10) - 1; // JS months are 0-indexed
        day = parseInt(ts.substr(6, 2), 10);
        hour = parseInt(ts.substr(8, 2), 10);
        minute = parseInt(ts.substr(10, 2), 10);
        second = parseInt(ts.substr(12, 2), 10);
        millisecond = parseInt(ts.substr(14, 3), 10);

        date = new Date(Date.UTC(year, month, day, hour, minute, second, millisecond));
        // console.log(`Parsed 17-digit timestamp: ${ts} → ${date.toISOString()}`);

        date.setSeconds(0, 0); // Round to minute
        return { date, valid: true, original: ts };
      }
      else {
        return { valid: false, original: ts };
      }
      
    } catch (e) {
      console.warn(`Failed to parse timestamp: ${ts}`, e);
      return { valid: false, original: ts };
    }
  },
  
  // Format dates consistently with flexible time inclusion
  format: (date, includeTime = false) => {
    if (!date) return '';
    
    try {
      // Ensure the date is rounded to the minute for consistency
      const roundedDate = new Date(date);
      roundedDate.setSeconds(0, 0);
      
      // Base format options
      const options = {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
      };
      
      // Add time components if requested
      if (includeTime) {
        options.hour = 'numeric';
        options.minute = '2-digit';
        options.hour12 = true;
      }
      
      const formatted = roundedDate.toLocaleString(undefined, options);
      
      // Apply consistent formatting with improved separators for readability
      if (includeTime) {
        // Format: Jan 5, 2023 • 2:30 PM
        return formatted.replace(/(\w+)\s+(\d+),\s+(\d+),?\s+(.+)/, '$1 $2, $3 • $4');
      } else {
        // Format: Jan 5, 2023
        return formatted.replace(/(\w+)\s+(\d+),\s+(\d+)/, '$1 $2, $3');
      }
    } catch (e) {
      console.warn('Error formatting date:', e);
      return String(date);
    }
  },
  
  // Format parsed timestamp result for display (date only)
  formatDate: (parsedTs) => {
    if (!parsedTs || !parsedTs.valid) {
      return parsedTs?.original?.substring(0, 10) || 'Invalid date'; 
    }
    return dateUtils.format(parsedTs.date);
  },
  
  // Format parsed timestamp result for display (with time)
  formatDateTime: (parsedTs) => {
    if (!parsedTs || !parsedTs.valid) {
      return parsedTs?.original || 'Invalid date';
    }
    return dateUtils.format(parsedTs.date, true);
  }
};

// ===== Rating Utils =====
export const ratingUtils = {
  // Format rating change for display (adding + for positive values)
  formatChange: (change) => {
    if (change === undefined || change === null) return '-';
    return change > 0 ? `+${change.toFixed(1)}` : change.toFixed(1);
  },
  
  // Get CSS class for rating change based on positive/negative value
  getChangeClass: (change) => {
    if (change === undefined || change === null) return '';
    return change > 0 ? 'positive-change' : 'negative-change';
  },
  
  // Calculate percentage values based on rating for visual indicators
  calculatePercentage: (rating, factor = 20) => {
    if (rating === undefined || rating === null) return 0;
    return Math.min(Math.max(rating * factor, 0), 100);
  },
  
  // Get rating color class based on value
  getRatingColorClass: (rating) => {
    if (rating === null || rating === undefined) return '';
    if (rating >= 4.5) return 'excellent-rating';
    if (rating >= 4.0) return 'good-rating';
    if (rating >= 3.0) return 'average-rating';
    return 'poor-rating';
  },
  
  // Process ratings history data to extract current rating, changes, and history details
  processHistory: (historyObj) => {
    if (!historyObj) {
      return {
        currentRating: null,
        latestChangeValue: null,
        latestChangeDisplay: null,
        latestChangePeriod: null,
        ratingHistoryDetails: ''
      };
    }
    
    // Parse and sort timestamps
    const timestampsWithDates = Object.keys(historyObj).map(ts => {
      return {
        timestamp: ts,
        parsed: dateUtils.parseTimestamp(ts),
        rating: historyObj[ts]
      };
    });
    
    // Sort by date
    const sortedTimestamps = timestampsWithDates.sort((a, b) => {
      if (a.parsed.valid && b.parsed.valid) {
        return a.parsed.date.getTime() - b.parsed.date.getTime();
      }
      return a.timestamp.localeCompare(b.timestamp);
    });
    
    const timestamps = sortedTimestamps.map(item => item.timestamp);
    
    // Initialize result object
    const result = {
      currentRating: null,
      ratingRangeValue: null,
      ratingRangeDisplay: null,
      ratingRangePeriod: null,
      ratingHistoryDetails: ''
    };
    
    // Process all ratings with timestamps and parse them
    const allRatings = timestamps
      .map(timestamp => ({
        timestamp,
        rating: historyObj[timestamp],
        parsed: dateUtils.parseTimestamp(timestamp)
      }))
      .filter(item => item.rating !== null && item.parsed.valid);
    
    if (allRatings.length === 0) {
      return result; // No valid ratings to process
    }
    
    // Sort all ratings by date
    allRatings.sort((a, b) => a.parsed.date - b.parsed.date);
    
    // Get the latest rating (most recent date)
    const latestRating = allRatings[allRatings.length - 1];
    result.currentRating = latestRating.rating;
    
    // Filter ratings from the past 6 months
    const sixMonthsAgo = new Date();
    sixMonthsAgo.setMonth(sixMonthsAgo.getMonth() - 6);
    const recentRatings = allRatings.filter(r => r.parsed.date >= sixMonthsAgo);
    const ratingsToUse = recentRatings.length > 0 ? recentRatings : allRatings;
    
    // Find lowest and highest ratings in the period
    const sortedByRating = [...ratingsToUse].sort((a, b) => a.rating - b.rating);
    const lowestRating = sortedByRating[0];
    const highestRating = sortedByRating[sortedByRating.length - 1];
    
    // Calculate rating difference based on latest rating position
    if (latestRating.rating > lowestRating.rating) {
      // If latest rating is higher than lowest, show improvement from lowest
      result.ratingRangeValue = latestRating.rating - lowestRating.rating;
    } else if (latestRating.rating < highestRating.rating) {
      // If latest rating is lower than highest, show drop from highest
      result.ratingRangeValue = latestRating.rating - highestRating.rating;
    } else {
      // If latest is both highest and lowest (or equal to both), show 0
      result.ratingRangeValue = 0;
    }
    
    // Format display value with sign (except for 0)
    result.ratingRangeDisplay = result.ratingRangeValue === 0 
      ? '0.0' 
      : (result.ratingRangeValue > 0 ? '+' : '') + result.ratingRangeValue.toFixed(1);
    
    // Store absolute value for sorting
    result.ratingDifferenceSortValue = Math.abs(result.ratingRangeValue);
    
    // Format date range for the entire history period
    const firstRating = allRatings[0];
    result.ratingRangePeriod = `${dateUtils.formatDate(firstRating.parsed)} → ${dateUtils.formatDate(latestRating.parsed)}`;
    
    // Prepare ratings for history details tooltip
    const uniqueRatings = [latestRating];
    
    // Add highest if different from latest
    if (highestRating !== latestRating) {
      uniqueRatings.push(highestRating);
    }
    
    // Add lowest if different from latest and highest
    if (lowestRating !== latestRating && lowestRating !== highestRating) {
      uniqueRatings.push(lowestRating);
    }
    
    // Add first record if different from others
    if (firstRating !== latestRating && firstRating !== highestRating && firstRating !== lowestRating) {
      uniqueRatings.push(firstRating);
    }
    
    // Sort by date for display in descending order (newest first)
    uniqueRatings.sort((a, b) => b.parsed.date - a.parsed.date);
    
    // Generate tooltip content with the selected ratings
    result.ratingHistoryDetails = ratingUtils.createHistoryTooltipContent(uniqueRatings);
    
    return result;
  },
  
  // Create detailed history for tooltip with cleaner logic and improved timestamp formatting
  // Shows most recent ratings first (reverse chronological order)
  createHistoryTooltipContent: (sortedItems) => {
    // Create a copy of the array to avoid mutating the original
    const items = [...sortedItems];
    // Reverse the array to show most recent first
    return items.reverse().map(item => {
      const { rating, parsed } = item;
      
      // Format timestamp with improved readability and minute rounding
      let dateStr;
      if (parsed.valid) {
        // Ensure the date is rounded to the minute
        const roundedDate = new Date(parsed.date);
        roundedDate.setSeconds(0, 0);
        
        // Create a more readable format with clear separators
        const options = {
          year: 'numeric',
          month: 'short',
          day: 'numeric',
          hour: 'numeric',
          minute: '2-digit',
          hour12: true
        };
        
        const formatted = roundedDate.toLocaleString(undefined, options);
        // Format as: Jan 5, 2023 • 2:30 PM (with bullet separator)
        dateStr = formatted.replace(/(\w+)\s+(\d+),\s+(\d+),?\s+(.+)/, '$1 $2, $3 • $4');
      } else {
        console.log("Invalid date format for timestamp:", parsed.original);
        // Fallback for invalid dates - try to format the original timestamp better
        const original = parsed.original || 'Invalid date';
        if (original.length === 14 && /^\d+$/.test(original)) {
          // Format YYYYMMDDHHMMSS as YYYY-MM-DD • HH:MM
          dateStr = `${original.substr(0, 4)}-${original.substr(4, 2)}-${original.substr(6, 2)} • ${original.substr(8, 2)}:${original.substr(10, 2)}`;
        } else if (original.length === 8 && /^\d+$/.test(original)) {
          // Format YYYYMMDD as YYYY-MM-DD
          dateStr = `${original.substr(0, 4)}-${original.substr(4, 2)}-${original.substr(6, 2)}`;
        } else {
          dateStr = original;
        }
      }
      
      const formattedRating = rating !== null ? rating.toFixed(1) : 'N/A';
      
      // Determine rating class based on value
      let ratingClass = ratingUtils.getRatingColorClass(rating);
      
      return `<span class="tooltip-date">${dateStr}</span>  →  <span class="tooltip-rating ${ratingClass}">${formattedRating}</span>`;
    })
    .reverse() // Show most recent first
    .join('<br>');
  }
};

// ===== UI Utils =====
export const tooltipUtils = {
  // Create and show tooltip with structured content
  show: (event, content) => {
    if (!content) return;
    
    // Remove any existing tooltip
    tooltipUtils.hide();
    
    // Create tooltip element with consistent structure
    const tooltip = document.createElement('div');
    tooltip.className = 'rating-tooltip';
    tooltip.innerHTML = `
      <div class="tooltip-title">Rating History</div>
      <div class="tooltip-content">${content}</div>
    `;
    
    // Add to document and position properly
    document.body.appendChild(tooltip);
    tooltipUtils.position(tooltip, event.target);
  },
  
  // Position tooltip relative to trigger element
  position: (tooltip, target) => {
    const rect = target.getBoundingClientRect();
    const viewportWidth = window.innerWidth;
    
    // Position tooltip below the target
    tooltip.style.top = `${rect.bottom + window.scrollY + 5}px`;
    
    // Adjust horizontal position to keep tooltip in viewport
    const tooltipWidth = tooltip.offsetWidth || 350; // Fallback to estimated width
    if (rect.left + tooltipWidth > viewportWidth - 20) {
      // Align tooltip right edge with viewport right edge (with padding)
      tooltip.style.left = 'auto';
      tooltip.style.right = '20px';
    } else {
      // Position tooltip aligned with target's left edge
      tooltip.style.left = `${rect.left + window.scrollX}px`;
      tooltip.style.right = 'auto';
    }
  },
  
  // Remove tooltip from DOM
  hide: () => {
    const existingTooltip = document.querySelector('.rating-tooltip');
    if (existingTooltip) {
      existingTooltip.remove();
    }
  }
};

// ===== Data Processing Utils =====
export const dataUtils = {
  // Format types for display
  formatTypes: (types) => {
    if (!types) return 'N/A';
    
    // Check if types is already a string
    if (typeof types === 'string') {
      try {
        // Try to parse it in case it's a JSON string
        const parsedTypes = JSON.parse(types);
        if (Array.isArray(parsedTypes)) {
          return parsedTypes
            .map(type => type.charAt(0).toUpperCase() + type.slice(1).replace('_', ' '))
            .join(', ');
        }
        return types;
      } catch (e) {
        // If it's not valid JSON, return as is
        return types;
      }
    }
    
    // If types is an array
    if (Array.isArray(types)) {
      return types
        .map(type => type.charAt(0).toUpperCase() + type.slice(1).replace('_', ' '))
        .join(', ');
    }
    
    // If it's neither a string nor an array, return as string
    return String(types);
  },
  
  // Format history_ratings JSON for better readability in CSV
  formatHistoryRatingsForCsv: (historyRatings) => {
    if (!historyRatings) return '';
    
    try {
      const historyObj = JSON.parse(historyRatings);
      
      // Convert to array of timestamps and sort chronologically
      return Object.entries(historyObj)
        .map(([ts, rating]) => {
          const parsedTs = dateUtils.parseTimestamp(ts);
          const formattedDate = dateUtils.formatDate(parsedTs);
          const formattedRating = rating !== null ? rating.toFixed(1) : 'N/A';
          return { date: parsedTs.valid ? parsedTs.date : new Date(0), text: `${formattedDate}: ${formattedRating}` };
        })
        .sort((a, b) => a.date - b.date) // Sort chronologically
        .map(item => item.text)
        .join('; ');
    } catch (e) {
      console.warn('Error formatting history for CSV:', e);
      return historyRatings;
    }
  }
};

// Simple helper for safely parsing JSON
export const safeJsonParse = (jsonString, defaultValue = {}) => {
  if (!jsonString) return defaultValue;
  
  try {
    return JSON.parse(jsonString);
  } catch (e) {
    console.warn('Error parsing JSON:', e);
    return defaultValue;
  }
};
