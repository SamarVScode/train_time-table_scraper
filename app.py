from flask import Flask, jsonify, request
from flask_cors import CORS
import re
import requests
from bs4 import BeautifulSoup
import os

app = Flask(__name__)
# Enable CORS so your frontend HTML can make API calls to this server
CORS(app) 

def clean_url(href):
    if not href: return ""
    if href.startswith('http://') or href.startswith('https://'): return href
    if href.startswith('//'): return f"https:{href}"
    prefix = "" if href.startswith('/') else "/"
    return f"https://indiarailinfo.com{prefix}{href}"

def live_scrape_app_json(train_number):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    search_url = f"https://indiarailinfo.com/blog?q={train_number}"
    try:
        res = requests.get(search_url, headers=headers, timeout=12)
        soup_search = BeautifulSoup(res.text, 'html.parser')
        timetable_url = None
        train_name = "Unknown Train"
        
        iri_pattern = re.compile(rf"train/.*-{train_number}/\d+")
        for link in soup_search.find_all('a', href=True):
            if iri_pattern.search(link['href']):
                timetable_url = clean_url(link['href'])
                train_name = link.text.strip().split("/", 1)[1].strip() if "/" in link.text else link.text.strip()
                break
                
        if not timetable_url:
            return {"success": False, "error": "Train not found on IndiaRailInfo."}

        timetable_res = requests.get(timetable_url, headers=headers, timeout=12)
        soup_table = BeautifulSoup(timetable_res.text, 'html.parser')
        
        table_container = soup_table.find('div', class_='newschtable')
        if not table_container:
            return {"success": False, "error": "Timetable layout could not be verified."}

        rows = table_container.find_all('div', recursive=False)
        
        current_quota = "GN"
        current_leg = "Origin"
        route_data = []
        
        for row in rows:
            cols = row.find_all('div', recursive=False)
            
            # A. PROCESS MAIN STATION ROWS
            if len(cols) >= 18:
                stop_number = cols[0].get_text(strip=True)
                if stop_number == "#" or not stop_number:
                    continue
                
                station_code = cols[2].get_text(strip=True)
                station_name = cols[3].get_text(strip=True)
                
                note_col = cols[5]
                if note_col.has_attr('title'):
                    title_text = note_col['title']
                    if "Remote Location Quota" in title_text:
                        current_quota = "RL"
                        current_leg = station_name
                    elif "Pooled Quota" in title_text:
                        current_quota = "PQ"
                        current_leg = station_name
                
                # Extract the Official Km from the hidden title attribute
                km_col = cols[13]
                span_tag = km_col.find('span')
                
                route_dist = km_col.get_text(strip=True)
                official_dist = route_dist 
                
                if span_tag and span_tag.has_attr('title'):
                    title_attr = span_tag['title']
                    if "Official Km:" in title_attr:
                        official_dist = title_attr.replace("Official Km:", "").strip()
                
                station_info = {
                    "stop": int(stop_number) if stop_number.isdigit() else stop_number,
                    "code": station_code,
                    "name": station_name,
                    "arr": cols[6].get_text(strip=True) or "-",
                    "dep": cols[8].get_text(strip=True) or "-",
                    "halt": cols[10].get_text(strip=True) or "-",
                    "pf": cols[11].get_text(strip=True) or "-",
                    "day": cols[12].get_text(strip=True) or "-",
                    "distance_covered": f"{official_dist} km" if official_dist else "-",
                    "quota": current_quota,
                    "leg": current_leg
                }
                
                route_data.append(station_info)
                
            # B. PROCESS INTERMEDIATE GAP ROWS
            elif 'intrmdtstn' in row.get('class', []):
                if len(cols) >= 5 and route_data:
                    inter_stops_text = cols[0].get_text(strip=True)
                    inter_time = cols[2].get_text(strip=True)
                    inter_dist = cols[4].get_text(strip=True)
                    
                    inter_count = inter_stops_text.split(' ')[0] if ' ' in inter_stops_text else "0"
                    
                    route_data[-1]["next_dist"] = f"{inter_dist} km" if inter_dist else "-"
                    route_data[-1]["next_time"] = inter_time if inter_time else "-"
                    route_data[-1]["intermediate_stops"] = int(inter_count) if inter_count.isdigit() else 0
                    
        # Clean up terminal station fields
        if route_data:
            route_data[-1]["quota"] = "Terminus"
            route_data[-1]["leg"] = "-"
            route_data[-1].pop("next_dist", None)
            route_data[-1].pop("next_time", None)
            route_data[-1].pop("intermediate_stops", None)

        return {
            "success": True,
            "train": train_number,
            "name": train_name,
            "total_stops": len(route_data),
            "route": route_data
        }

    except Exception as e:
        return {"success": False, "error": f"Scraping Error: {str(e)}"}

# --- API ROUTES ---

@app.route('/api/train/<train_number>', methods=['GET'])
def get_train_data(train_number):
    """Endpoint to fetch train timetable data as JSON"""
    if len(train_number) == 5 and train_number.isdigit():
        result = live_scrape_app_json(train_number)
        return jsonify(result)
    return jsonify({"success": False, "error": "Invalid Train Number format. Must be 5 digits."}), 400

@app.route('/', methods=['GET'])
def home():
    """Simple health check route"""
    return "IndiaRailInfo Scraper API is Running Successfully!"

if __name__ == '__main__':
    # Railway passes the PORT variable dynamically
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
