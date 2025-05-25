#!/usr/bin/env python3
"""
Client for interacting with Google Places API
"""

import logging
import requests
import time
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class GooglePlacesClient:
    """Client for interacting with Google Places API"""
    
    NEARBY_SEARCH_URL = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
    PLACE_DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"
    
    def __init__(self, api_key: str):
        """
        Initialize the client
        
        Args:
            api_key: Google Maps API key
        """
        self.api_key = api_key
    
    def search_nearby_places(
        self,
        location_lat: float,
        location_lng: float,
        radius: int,
        keyword: str = "咖啡 飲料"
    ) -> List[Dict[str, Any]]:
        """
        Search for places near a location
        
        Args:
            location_lat: Latitude of the search location
            location_lng: Longitude of the search location
            radius: Search radius in meters
            keyword: Type of place to search for (default: cafe)
            
        Returns:
            List of places found
        """
        params = {
            "location": f"{location_lat},{location_lng}",
            "radius": radius,
            "keyword": keyword,
            "language": "zh-TW",
            "key": self.api_key
        }
        
        all_results = []
        next_page_token = None
        
        try:
            while True:
                if next_page_token:
                    # Add page token to parameters if we have one
                    params["pagetoken"] = next_page_token
                    # Google requires a delay between requests when using page tokens
                    time.sleep(2)
                
                response = requests.get(self.NEARBY_SEARCH_URL, params=params)
                response.raise_for_status()
                data = response.json()
                
                if data["status"] != "OK" and data["status"] != "ZERO_RESULTS":
                    logger.error(f"Error in nearby search: {data['status']}")
                    if "error_message" in data:
                        logger.error(f"Error message: {data['error_message']}")
                    break
                
                # Add results from this page
                results = data.get("results", [])
                all_results.extend(results)
                
                # Check if there are more pages
                next_page_token = data.get("next_page_token")
                if not next_page_token:
                    break
            
            return all_results
            
        except Exception as e:
            logger.error(f"Error searching nearby places: {str(e)}")
            return all_results if all_results else []
    
    def get_place_details(self, place_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a specific place
        
        Args:
            place_id: Google Places ID
            
        Returns:
            Place details or None if error occurs
        """
        params = {
            "place_id": place_id,
            "key": self.api_key,
            "fields": "name,formatted_address,website,rating,reviews,url"
        }
        
        try:
            response = requests.get(self.PLACE_DETAILS_URL, params=params)
            response.raise_for_status()
            data = response.json()
            
            if data["status"] != "OK":
                logger.error(f"Error getting place details: {data['status']}")
                if "error_message" in data:
                    logger.error(f"Error message: {data['error_message']}")
                return None
            
            return data.get("result")
            
        except Exception as e:
            logger.error(f"Error getting place details: {str(e)}")
            return None
    
    def enrich_places(self, places: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Enrich places data with detailed information
        
        Args:
            places: List of places from nearby search
            
        Returns:
            List of enriched place data
        """
        enriched_places = []
        
        for place in places:
            if "place_id" not in place:
                continue
                
            details = self.get_place_details(place["place_id"])
            if details:
                # Merge basic and detailed information
                enriched_place = {**place, **details}
                enriched_places.append(enriched_place)
            else:
                # If details fetch fails, use basic information
                enriched_places.append(place)
        
        return enriched_places 