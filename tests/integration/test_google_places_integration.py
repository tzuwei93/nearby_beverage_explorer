import os
import pytest
# Import using src.docker pattern for local testing
from src.docker.google_places_collector.google_places_client import GooglePlacesClient

# Skip all tests if no API key is available
pytestmark = pytest.mark.skipif(
    'GOOGLE_MAPS_API_KEY' not in os.environ,
    reason="Google Maps API key not found in environment variables"
)

@pytest.fixture
def client():
    """Fixture providing a GooglePlacesClient instance with real API key"""
    api_key = os.environ.get('GOOGLE_MAPS_API_KEY')
    return GooglePlacesClient(api_key)

@pytest.mark.integration
def test_nearby_search_response_structure(client):
    """Test the structure of nearby search response from the actual API"""

    results = client.search_nearby_places(
        location_lat=25.041171,
        location_lng=121.565227,
        radius=500,
    )
    
    # Verify we got results
    assert len(results) > 0
    
    # Verify structure of each place
    for place in results:
        # Required fields
        assert 'place_id' in place
        assert 'name' in place
        assert 'geometry' in place
        assert 'location' in place['geometry']
        assert 'lat' in place['geometry']['location']
        assert 'lng' in place['geometry']['location']
        
@pytest.mark.integration
def test_place_details_response_structure(client):
    """Test the structure of place details response from the actual API"""
    # First get a place_id from nearby search
    places = client.search_nearby_places(
        location_lat=25.041171,
        location_lng=121.565227,
        radius=500,
    )
    
    assert len(places) > 0
    place_id = places[0]['place_id']
    
    # Get details for the place
    details = client.get_place_details(place_id)
    print (details)
    
    assert details is not None
    assert 'name' in details
    assert isinstance(details['name'], str)
    assert isinstance(details['rating'], (int, float))
    assert isinstance(details['formatted_address'], str)

@pytest.mark.integration
def test_pagination_with_real_data(client):
    """Test pagination behavior with real API responses"""
    # Request more results than what comes in a single page (20 is max per page)
    results = client.search_nearby_places(
        location_lat=25.041171,
        location_lng=121.565227,
        radius=1000,
    )
    
    # Verify we got more results than a single page would provide
    print (len(results))
    assert len(results) > 20, "Expected more than 20 results to test pagination"
    
    # Verify all results have the required structure
    place_ids = set()
    for place in results:
        assert 'place_id' in place
        assert 'name' in place
        # Verify no duplicate places
        assert place['place_id'] not in place_ids
        place_ids.add(place['place_id']) 
        