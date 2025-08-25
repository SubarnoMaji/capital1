"""
SoilGrids API client for fetching soil data
"""

import requests
import time
from typing import Dict, Optional, Any
from models import SoilProperties, LocationInfo
from config import SOILGRIDS_BASE_URL, SOIL_PROPERTIES, DEFAULT_VALUES
from utils import convert_soil_property, print_progress, handle_api_error


class SoilGridsAPI:
    """Client for interacting with SoilGrids API"""
    
    def __init__(self, base_url: str = SOILGRIDS_BASE_URL, timeout: int = 30, retry_count: int = 3):
        """
        Initialize SoilGrids API client
        
        Args:
            base_url: Base URL for SoilGrids API
            timeout: Request timeout in seconds
            retry_count: Number of retries for failed requests
        """
        self.base_url = base_url
        self.classification_url = "https://rest.isric.org/soilgrids/v2.0/classification/query"
        self.timeout = timeout
        self.retry_count = retry_count
        self.session = requests.Session()
        
        # Set default headers
        self.session.headers.update({
            'User-Agent': 'SoilAnalysisTool/1.0',
            'Accept': 'application/json'
        })
    
    def fetch_property(self, property_name: str, lat: float, lon: float, depth: str = "0-30cm") -> Optional[float]:
        """
        Fetch a single soil property from SoilGrids API
        
        Args:
            property_name: Name of soil property to fetch
            lat: Latitude
            lon: Longitude
            depth: Soil depth layer
            
        Returns:
            Property value or None if failed
        """
        params = {
            "lat": lat,
            "lon": lon,
            "property": property_name,
            "depth": depth,
            "value": "mean"
        }
        
        for attempt in range(self.retry_count):
            try:
                response = self.session.get(
                    self.base_url, 
                    params=params, 
                    timeout=self.timeout
                )
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Navigate through the nested JSON structure
                    if 'properties' in data and 'layers' in data['properties']:
                        layers = data['properties']['layers']
                        if layers and 'depths' in layers[0]:
                            depths = layers[0]['depths']
                            if depths and 'values' in depths[0]:
                                values = depths[0]['values']
                                if values and 'mean' in values:
                                    return values['mean']
                
                elif response.status_code == 429:  # Rate limited
                    wait_time = 2 ** attempt  # Exponential backoff
                    print(f"⏸️  Rate limited, waiting {wait_time} seconds...")
                    time.sleep(wait_time)
                    continue
                    
                else:
                    error_msg = handle_api_error(response, property_name)
                    print(f"❌ {error_msg}")
                    
            except requests.exceptions.Timeout:
                print(f"⏱️  Timeout fetching {property_name} (attempt {attempt + 1})")
                if attempt < self.retry_count - 1:
                    time.sleep(1)
                    
            except requests.exceptions.RequestException as e:
                print(f"🌐 Network error fetching {property_name}: {str(e)}")
                if attempt < self.retry_count - 1:
                    time.sleep(1)
                    
            except Exception as e:
                print(f"❌ Unexpected error fetching {property_name}: {str(e)}")
                break
        
        return None
    
    def fetch_all_properties_single_request(self, location: LocationInfo) -> Dict[str, Optional[float]]:
        """
        Fetch all soil properties in a single API request (more efficient)
        
        Args:
            location: LocationInfo object containing coordinates and depth
            
        Returns:
            Dictionary of property names to values
        """
        print_progress("Fetching all soil properties from SoilGrids API...")
        
        params = {
            "lat": location.latitude,
            "lon": location.longitude,
            "depth": location.depth,
            "value": "mean"
        }
        
        for attempt in range(self.retry_count):
            try:
                response = self.session.get(
                    self.base_url, 
                    params=params, 
                    timeout=self.timeout
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return self._parse_properties_response(data)
                    
                elif response.status_code == 429:  # Rate limited
                    wait_time = 2 ** attempt
                    print(f"⏸️  Rate limited, waiting {wait_time} seconds...")
                    time.sleep(wait_time)
                    continue
                    
                else:
                    error_msg = handle_api_error(response, "all properties")
                    print(f"❌ {error_msg}")
                    
            except requests.exceptions.Timeout:
                print(f"⏱️  Timeout fetching properties (attempt {attempt + 1})")
                if attempt < self.retry_count - 1:
                    time.sleep(2)
                    
            except requests.exceptions.RequestException as e:
                print(f"🌐 Network error: {str(e)}")
                if attempt < self.retry_count - 1:
                    time.sleep(2)
                    
            except Exception as e:
                print(f"❌ Unexpected error: {str(e)}")
                break
        
        # Return empty dict if all attempts failed
        return {prop: None for prop in SOIL_PROPERTIES}
    
    def _parse_properties_response(self, data: Dict) -> Dict[str, Optional[float]]:
        """
        Parse the properties API response based on the structure you provided
        
        Args:
            data: API response data
            
        Returns:
            Dictionary of property names to values
        """
        soil_data = {}
        
        if 'properties' in data and 'layers' in data['properties']:
            layers = data['properties']['layers']
            
            for layer in layers:
                prop_name = layer.get('name')
                if prop_name in SOIL_PROPERTIES:
                    if 'depths' in layer and layer['depths']:
                        depth_data = layer['depths'][0]  # Get first depth
                        if 'values' in depth_data and 'mean' in depth_data['values']:
                            soil_data[prop_name] = depth_data['values']['mean']
        
        # Ensure all properties are present (set to None if missing)
        for prop in SOIL_PROPERTIES:
            if prop not in soil_data:
                soil_data[prop] = None
                
        return soil_data
    
    def fetch_soil_classification(self, lat: float, lon: float) -> Dict[str, Any]:
        """
        Fetch soil classification data from SoilGrids classification API
        
        Args:
            lat: Latitude
            lon: Longitude
            
        Returns:
            Dictionary containing classification data
        """
        params = {
            "lat": lat,
            "lon": lon
        }
        
        for attempt in range(self.retry_count):
            try:
                response = self.session.get(
                    self.classification_url,
                    params=params,
                    timeout=self.timeout
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return {
                        'class_name': data.get('wrb_class_name', 'Unknown'),
                        'class_value': data.get('wrb_class_value', 0),
                        'probabilities': data.get('wrb_class_probability', []),
                        'coordinates': data.get('coordinates', [lon, lat]),
                        'query_time': data.get('query_time_s', 0)
                    }
                    
                elif response.status_code == 429:  # Rate limited
                    wait_time = 2 ** attempt
                    print(f"⏸️  Rate limited for classification, waiting {wait_time} seconds...")
                    time.sleep(wait_time)
                    continue
                    
                else:
                    error_msg = handle_api_error(response, "classification")
                    print(f"❌ {error_msg}")
                    
            except Exception as e:
                print(f"❌ Error fetching classification: {str(e)}")
                if attempt < self.retry_count - 1:
                    time.sleep(1)
        
        # Return default classification if failed
        return {
            'class_name': 'Unknown',
            'class_value': 0,
            'probabilities': [],
            'coordinates': [lon, lat],
            'query_time': 0
        }
    def fetch_all_properties(self, location: LocationInfo) -> Dict[str, Optional[float]]:
        """
        Fetch all soil properties for a location
        First try the efficient single request, fall back to individual requests if needed
        
        Args:
            location: LocationInfo object containing coordinates and depth
            
        Returns:
            Dictionary of property names to values
        """
        # Try the efficient single request first
        soil_data = self.fetch_all_properties_single_request(location)
        
        # Check how many properties were successfully retrieved
        successful_props = sum(1 for v in soil_data.values() if v is not None)
        
        # If we got most properties, use this data
        if successful_props >= len(SOIL_PROPERTIES) * 0.7:  # At least 70% success rate
            print(f"✅ Retrieved {successful_props}/{len(SOIL_PROPERTIES)} properties in single request")
            return soil_data
        
        # Fall back to individual property requests
        print("⚠️  Single request incomplete, trying individual property requests...")
        return self._fetch_properties_individually(location)
    
    def parse_soil_data(self, raw_data: Dict[str, Optional[float]]) -> SoilProperties:
        """
        Parse raw soil data into SoilProperties object
        
        Args:
            raw_data: Dictionary of raw property values
            
        Returns:
            SoilProperties object
        """
        return SoilProperties(
            ph=convert_soil_property("phh2o", raw_data.get("phh2o")),
            organic_carbon=convert_soil_property("soc", raw_data.get("soc")),
            nitrogen=convert_soil_property("nitrogen", raw_data.get("nitrogen")),
            phosphorus=convert_soil_property("phosporus", raw_data.get("phosporus")),
            potassium=convert_soil_property("potassium", raw_data.get("potassium")),
            clay_content=convert_soil_property("clay", raw_data.get("clay")),
            sand_content=convert_soil_property("sand", raw_data.get("sand")),
            silt_content=convert_soil_property("silt", raw_data.get("silt")),
            bulk_density=convert_soil_property("bdod", raw_data.get("bdod")),
            cation_exchange_capacity=convert_soil_property("cec", raw_data.get("cec"))
        )
    
    def _fetch_properties_individually(self, location: LocationInfo) -> Dict[str, Optional[float]]:
        """
        Fetch properties one by one (fallback method)
        
        Args:
            location: LocationInfo object
            
        Returns:
            Dictionary of property names to values
        """
        soil_data = {}
        total_properties = len(SOIL_PROPERTIES)
        
        for i, prop in enumerate(SOIL_PROPERTIES, 1):
            print_progress(f"Fetching {prop}...", i, total_properties)
            
            value = self.fetch_property(
                prop, 
                location.latitude, 
                location.longitude, 
                location.depth
            )
            
            soil_data[prop] = value
            
            # Add small delay to be respectful to API
            time.sleep(0.2)
        
        return soil_data
    
    def get_soil_analysis(self, location: LocationInfo) -> tuple[SoilProperties, Dict[str, Optional[float]], Dict[str, Any]]:
        """
        Get complete soil analysis for a location including classification
        
        Args:
            location: LocationInfo object
            
        Returns:
            Tuple of (SoilProperties, raw_data_dict, classification_data)
        """
        # Fetch soil properties
        raw_data = self.fetch_all_properties(location)
        
        # Fetch soil classification
        print_progress("Fetching soil classification...")
        classification_data = self.fetch_soil_classification(location.latitude, location.longitude)
        
        # Parse into structured format
        soil_properties = self.parse_soil_data(raw_data)
        
        # Log summary
        successful_fetches = sum(1 for v in raw_data.values() if v is not None)
        total_properties = len(SOIL_PROPERTIES)
        
        print(f"✅ Successfully fetched {successful_fetches}/{total_properties} soil properties")
        print(f"✅ Soil classification: {classification_data['class_name']}")
        
        if successful_fetches < total_properties:
            missing_props = [prop for prop, value in raw_data.items() if value is None]
            print(f"⚠️  Using default values for: {', '.join(missing_props)}")
        
        return soil_properties, raw_data, classification_data
    
    def check_api_status(self) -> bool:
        """
        Check if SoilGrids API is accessible
        
        Returns:
            True if API is accessible, False otherwise
        """
        try:
            # Try a simple request to check API status
            test_params = {
                "lat": 0,
                "lon": 0,
                "property": "phh2o",
                "depth": "0-5cm",
                "value": "mean"
            }
            
            response = self.session.get(
                self.base_url, 
                params=test_params, 
                timeout=10
            )
            
            return response.status_code in [200, 400]  # 400 might be expected for test coordinates
            
        except Exception:
            return False
    
    def get_available_depths(self) -> list:
        """
        Get list of available soil depths
        
        
        Returns:
            List of available depth strings
        """
        from config import AVAILABLE_DEPTHS
        return AVAILABLE_DEPTHS.copy()
    
    def close(self):
        """Close the session"""
        self.session.close()