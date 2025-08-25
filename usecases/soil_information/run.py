#!/usr/bin/env python3
"""
Quick run script for the Soil Analysis Tool
Provides a simple interface to run common analyses
"""

import sys
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from soil_analyzer import SoilAnalyzer
from config import get_openai_api_key
from utils import validate_coordinates


def quick_analysis(lat, lon, depth="0-30cm"):
    """Run a quick soil analysis"""
    # Validate coordinates
    is_valid, error_msg = validate_coordinates(lat, lon)
    if not is_valid:
        print(f"❌ {error_msg}")
        return
    
    # Get API key
    api_key = get_openai_api_key()
    if not api_key:
        print("❌ OpenAI API key not found. Please set OPENAI_API_KEY environment variable.")
        return
    
    try:
        # Initialize analyzer
        analyzer = SoilAnalyzer(api_key)
        
        # Run analysis
        print(f"🌱 Running soil analysis for {lat}, {lon} at depth {depth}")
        print("=" * 60)
        
        analysis_result = analyzer.analyze_location(lat, lon, depth)
        
        # Generate and display report
        report = analyzer.generate_report(analysis_result)
        print(report)
    
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
    finally:
        if 'analyzer' in locals():
            analyzer.close()


if __name__ == "__main__":
    lat = float(input("Enter the latitude: "))
    lon = float(input("Enter the longitude: "))
    depth = "0-5cm"
    quick_analysis(lat, lon, depth)