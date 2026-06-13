import sys
import json
import os

# Add the current directory to sys.path to allow running as a script or module
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from parsers.confirmtkt import ConfirmTktParser
except ImportError:
    # Fallback for different execution contexts
    from .parsers.confirmtkt import ConfirmTktParser

def main():
    if len(sys.argv) < 7:
        print("Usage: python -m availability_scraper.main <train_no> <date> <from> <to> <class> <quota>")
        print("Example: python -m availability_scraper.main 12002 25-06-2024 NDLS VGLB CC GN")
        return

    train_no = sys.argv[1]
    date = sys.argv[2]
    from_stn = sys.argv[3]
    to_stn = sys.argv[4]
    travel_class = sys.argv[5]
    quota = sys.argv[6]

    print(f"--- Fetching Availability for {train_no} ---")
    print(f"Route: {from_stn} -> {to_stn} | Date: {date} | Class: {travel_class} | Quota: {quota}")
    
    # Generate the search URL requested by user
    search_url = ConfirmTktParser.generate_search_url(from_stn, to_stn, date)
    print(f"Search URL: {search_url}")
    print("-" * 40)
    
    result = ConfirmTktParser.get_availability(
        train_no, from_stn, to_stn, date, travel_class, quota
    )
    
    print("\nResult:")
    print(json.dumps(result.to_dict(), indent=2))

if __name__ == "__main__":
    main()
