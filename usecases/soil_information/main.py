#!/usr/bin/env python3
"""
Main entry point for the Soil Analysis and Crop Recommendation Tool
"""

import os
import sys
from typing import List, Tuple
from dotenv import load_dotenv

from soil_analyzer import SoilAnalyzer
from config import get_openai_api_key, AVAILABLE_DEPTHS
from utils import validate_coordinates

# Load environment variables
load_dotenv()


def get_api_key() -> str:
    """Get OpenAI API key from environment or user input"""
    api_key = get_openai_api_key()
    
    if not api_key:
        print("🔑 OpenAI API Key Required")
        print("-" * 30)
        print("You can either:")
        print("1. Set OPENAI_API_KEY environment variable")
        print("2. Create a .env file with: OPENAI_API_KEY=your-key-here")
        print("3. Enter it now when prompted")
        print()
        
        api_key = input("Please enter your OpenAI API key: ").strip()
        
        if not api_key:
            print("❌ API key is required to run this tool")
            sys.exit(1)
    
    return api_key


def get_coordinates() -> Tuple[float, float]:
    """Get coordinates from user input with validation"""
    while True:
        try:
            print("📍 Enter Location Coordinates")
            print("-" * 30)
            
            # Provide some example coordinates
            print("Examples:")
            print("• New Delhi, India: 28.6139, 77.2090")
            print("• Iowa, USA: 41.8780, -93.0977")
            print("• São Paulo, Brazil: -23.5505, -46.6333")
            print("• Your coordinates: 22.33, 87.33 (example from your original code)")
            print()
            
            lat_input = input("Enter latitude (-90 to 90): ").strip()
            lon_input = input("Enter longitude (-180 to 180): ").strip()
            
            latitude = float(lat_input)
            longitude = float(lon_input)
            
            # Validate coordinates
            is_valid, error_msg = validate_coordinates(latitude, longitude)
            if not is_valid:
                print(f"❌ {error_msg}")
                print("Please try again.\n")
                continue
            
            return latitude, longitude
            
        except ValueError:
            print("❌ Please enter valid numeric coordinates")
            print("Please try again.\n")
            continue
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            sys.exit(0)


def get_soil_depth() -> str:
    """Get soil depth from user input"""
    print("\n📏 Select Soil Depth Layer")
    print("-" * 30)
    
    for i, depth in enumerate(AVAILABLE_DEPTHS, 1):
        print(f"{i}. {depth}")
    
    print(f"{len(AVAILABLE_DEPTHS) + 1}. Custom depth")
    print()
    
    while True:
        try:
            choice = input(f"Select depth (1-{len(AVAILABLE_DEPTHS) + 1}, default: 2 for 0-30cm): ").strip()
            
            if not choice:
                return "0-30cm"  # Default choice
            
            choice_num = int(choice)
            
            if 1 <= choice_num <= len(AVAILABLE_DEPTHS):
                return AVAILABLE_DEPTHS[choice_num - 1]
            elif choice_num == len(AVAILABLE_DEPTHS) + 1:
                custom_depth = input("Enter custom depth (e.g., 0-15cm): ").strip()
                return custom_depth if custom_depth else "0-30cm"
            else:
                print(f"Please enter a number between 1 and {len(AVAILABLE_DEPTHS) + 1}")
                
        except ValueError:
            print("Please enter a valid number")
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            sys.exit(0)


def show_main_menu() -> str:
    """Show main menu and get user choice"""
    print("\n🌾 SOIL ANALYSIS TOOL - MAIN MENU")
    print("=" * 40)
    print("1. Full Soil Analysis & Crop Recommendations")
    print("2. Quick Soil Analysis")
    print("3. Fertilizer Recommendations Only")
    print("4. Compare Multiple Locations")
    print("5. Exit")
    print()
    
    return input("Select option (1-5): ").strip()


def handle_full_analysis(analyzer: SoilAnalyzer):
    """Handle full soil analysis workflow"""
    latitude, longitude = get_coordinates()
    depth = get_soil_depth()
    
    # Perform analysis
    try:
        analysis_result = analyzer.analyze_location(latitude, longitude, depth)
    except Exception as e:
        print(f"❌ Error during analysis: {e}")
        return

    # Generate and display report
    try:
        report = analyzer.generate_report(analysis_result)
        print(report)
    except Exception as e:
        print(f"❌ Error generating report: {e}")
        return

    # Ask to save report
    print("\n💾 Save Options")
    print("-" * 15)
    print("1. Save as text file")
    print("2. Save as JSON data")
    print("3. Save both formats")
    print("4. Don't save")