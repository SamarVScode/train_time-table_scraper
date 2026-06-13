import sys
import os
# Add root directory to sys.path to ensure availability_scraper imports resolve correctly
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import re
import requests
from bs4 import BeautifulSoup
import os
from dotenv import load_dotenv
from supabase import create_client, Client

# Load environment variables
load_dotenv()

# Configure Flask to use the 'static' folder
app = Flask(__name__, static_folder='../static')
CORS(app)

# Supabase setup
url: str = os.environ.get("SUPABASE_URL", "")
key: str = os.environ.get("SUPABASE_KEY", "")
supabase: Client = None

if url and key:
    supabase = create_client(url, key)

def clean_url(href, base="https://indiarailinfo.com"):
    if not href:
        return ""
    if href.startswith(('http://', 'https://')):
        return href
    if href.startswith('//'):
        return f"https:{href}"
    prefix = "" if href.startswith('/') else "/"
    return f"{base}{prefix}{href}"

def scrape_train_data(train_number):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    search_url = f"https://indiarailinfo.com/blog?q={train_number}"

    # ScraperAPI configuration
    scraperapi_key = os.environ.get('SCRAPERAPI_KEY', '2489929e94aa0f1851699927d4155daf')
    scraperapi_endpoint = 'https://api.scraperapi.com/'

    try:
        payload = {'api_key': scraperapi_key, 'url': search_url}
        res = requests.get(scraperapi_endpoint, params=payload, headers=headers, timeout=30)
        res.raise_for_status()
        raw_html = res.text

        timetable_url = None
        train_name = f"Train {train_number}"

        found_links = re.findall(rf'href=["\'](/train/[^"\']+?{train_number}(?:/\d+)*)["\']', raw_html)

        if not found_links:
            soup_search = BeautifulSoup(raw_html, 'html.parser')
            for link in soup_search.find_all('a', href=True):
                href = link['href']
                text = link.get_text(strip=True)
                if train_number in text or f"-{train_number}" in href:
                    match = re.search(r'/(\d+)(?:/\d+)*$', href)
                    if match:
                        found_links.append(href)

        if found_links:
            clean_target = list(set(found_links))[0]
            id_extract = re.search(r'/train/(\d+)|/(\d+)(?:/\d+)*$', clean_target)
            if id_extract:
                train_id = id_extract.group(1) or id_extract.group(2)
                timetable_url = f"https://indiarailinfo.com/train/{train_id}"

        if not timetable_url:
            return {
                "success": False,
                "error": f"Train {train_number} not found on IndiaRailInfo",
                "train_number": train_number
            }

        timetable_payload = {'api_key': scraperapi_key, 'url': timetable_url}
        timetable_res = requests.get(scraperapi_endpoint, params=timetable_payload, headers=headers, timeout=30)
        timetable_res.raise_for_status()
        soup_table = BeautifulSoup(timetable_res.text, 'html.parser')

        heading = soup_table.find('h1') or soup_table.find('h2')
        if heading:
            raw_title = heading.get_text(strip=True)
            name_match = re.search(rf'(?:{train_number}/|⇒\s*{train_number}/)?([^(\n\r]+)', raw_title)
            if name_match:
                train_name = name_match.group(1).strip()

        table_container = soup_table.find('div', class_='newschtable') or soup_table.find('div', class_='ttable')
        if not table_container:
            table_container = soup_table.find('div', id=re.compile(r'.*table.*'))

        if not table_container:
            return {
                "success": False,
                "error": "Could not parse timetable. Website layout may have changed.",
                "train_number": train_number
            }

        rows = table_container.find_all('div', recursive=False)
        route_data = []
        current_quota = "GN"
        current_leg = "Origin"

        for row in rows:
            cols = row.find_all('div', recursive=False)

            if len(cols) >= 10:
                stop_num_text = cols[0].get_text(strip=True)
                if stop_num_text == "#" or not stop_num_text or not stop_num_text.isdigit():
                    continue

                station_code = cols[2].get_text(strip=True) if len(cols) > 2 else "-"
                station_name = cols[3].get_text(strip=True) if len(cols) > 3 else "-"

                if len(cols) > 5:
                    note_col = cols[5]
                    if note_col.has_attr('title'):
                        title = note_col['title'].lower()
                        if "remote location quota" in title:
                            current_quota = "RL"
                            current_leg = station_name
                        elif "pooled quota" in title:
                            current_quota = "PQ"
                            current_leg = station_name

                official_dist = "-"
                if len(cols) > 13:
                    km_col = cols[13]
                    text_data = km_col.get_text(strip=True)
                    span = km_col.find('span')
                    if span and span.has_attr('title') and "Official Km:" in span['title']:
                        official_dist = span['title'].split("Official Km:")[-1].strip()
                    elif text_data:
                        official_dist = text_data.replace("km", "").strip()

                if official_dist == "-" or not official_dist:
                    for col in cols:
                        text_data = col.get_text(strip=True)
                        if "km" in text_data.lower():
                            span = col.find('span')
                            if span and span.has_attr('title') and "Official Km:" in span['title']:
                                official_dist = span['title'].split("Official Km:")[-1].strip()
                            else:
                                official_dist = text_data.replace("km", "").strip()
                            break

                station_entry = {
                    "stop": int(stop_num_text),
                    "code": station_code,
                    "name": station_name,
                    "arrival": cols[6].get_text(strip=True) if len(cols) > 6 else "-",
                    "departure": cols[8].get_text(strip=True) if len(cols) > 8 else "-",
                    "halt_time": cols[10].get_text(strip=True) if len(cols) > 10 else "-",
                    "platform": cols[11].get_text(strip=True) if len(cols) > 11 else "-",
                    "day": cols[12].get_text(strip=True) if len(cols) > 12 else "1",
                    "distance_covered": f"{official_dist} km" if official_dist and official_dist != "-" else "-",
                    "quota": current_quota,
                    "leg_from": current_leg
                }
                route_data.append(station_entry)

            elif 'intrmdtstn' in row.get('class', []):
                if len(cols) >= 3 and route_data:
                    stops_text = cols[0].get_text(strip=True)
                    time_text = cols[2].get_text(strip=True)
                    dist_text = cols[4].get_text(strip=True) if len(cols) > 4 else ""

                    if not dist_text:
                        for col in cols:
                            t = col.get_text(strip=True)
                            if "km" in t.lower():
                                dist_text = t
                                break

                    dist_clean = dist_text.replace("km", "").strip() if dist_text else "-"
                    stop_count = stops_text.split()[0] if ' ' in stops_text else "0"

                    route_data[-1]["next_segment"] = {
                        "intermediate_stops": int(stop_count) if stop_count.isdigit() else 0,
                        "travel_time": time_text or "-",
                        "distance_covered": f"{dist_clean} km" if dist_clean != "-" else "-"
                    }

        if route_data:
            route_data[-1]["quota"] = "Terminus"
            route_data[-1]["leg_from"] = "-"
            route_data[-1].pop("next_segment", None)

        return {
            "success": True,
            "train_number": train_number,
            "train_name": train_name,
            "total_stations": len(route_data),
            "source": route_data[0]["name"] if route_data else "-",
            "destination": route_data[-1]["name"] if route_data else "-",
            "route": route_data
        }

    except requests.exceptions.Timeout:
        return {"success": False, "error": "Request timed out", "train_number": train_number}
    except requests.exceptions.ConnectionError:
        return {"success": False, "error": "Failed to connect to IndiaRailInfo", "train_number": train_number}
    except Exception as e:
        return {"success": False, "error": f"Error: {str(e)}", "train_number": train_number}

def save_to_supabase(data):
    if not supabase:
        return
    
    try:
        # Save to trains table
        train_info = {
            "train_number": data["train_number"],
            "train_name": data["train_name"],
            "total_stations": data["total_stations"],
            "source_station": data["source"],
            "destination_station": data["destination"]
        }
        supabase.table("trains").upsert(train_info).execute()

        # Save to train_routes table
        route_entries = []
        for stop in data["route"]:
            entry = {
                "train_number": data["train_number"],
                "stop_number": stop["stop"],
                "station_code": stop["code"],
                "station_name": stop["name"],
                "arrival_time": stop["arrival"],
                "departure_time": stop["departure"],
                "halt_time": stop["halt_time"],
                "platform": stop["platform"],
                "day_count": stop["day"],
                "distance_covered": stop["distance_covered"],
                "quota": stop["quota"],
                "leg_from": stop["leg_from"]
            }
            
            if "next_segment" in stop:
                entry["next_segment_intermediate_stops"] = stop["next_segment"].get("intermediate_stops")
                entry["next_segment_travel_time"] = stop["next_segment"].get("travel_time")
                entry["next_segment_distance_covered"] = stop["next_segment"].get("distance_covered")
            
            route_entries.append(entry)
        
        if route_entries:
            supabase.table("train_routes").upsert(route_entries).execute()
            
    except Exception as e:
        print(f"Error saving to Supabase: {e}")

def get_from_supabase(train_number):
    if not supabase:
        return None
    
    try:
        # Fetch train info
        train_res = supabase.table("trains").select("*").eq("train_number", train_number).execute()
        if not train_res.data:
            return None
        
        train_info = train_res.data[0]
        
        # Fetch route details
        route_res = supabase.table("train_routes").select("*").eq("train_number", train_number).order("stop_number").execute()
        
        route_data = []
        for row in route_res.data:
            stop = {
                "stop": row["stop_number"],
                "code": row["station_code"],
                "name": row["station_name"],
                "arrival": row["arrival_time"],
                "departure": row["departure_time"],
                "halt_time": row["halt_time"],
                "platform": row["platform"],
                "day": row["day_count"],
                "distance_covered": row["distance_covered"],
                "quota": row["quota"],
                "leg_from": row["leg_from"]
            }
            
            if row.get("next_segment_travel_time"):
                stop["next_segment"] = {
                    "intermediate_stops": row["next_segment_intermediate_stops"],
                    "travel_time": row["next_segment_travel_time"],
                    "distance_covered": row["next_segment_distance_covered"]
                }
            route_data.append(stop)
            
        return {
            "success": True,
            "train_number": train_info["train_number"],
            "train_name": train_info["train_name"],
            "total_stations": train_info["total_stations"],
            "source": train_info["source_station"],
            "destination": train_info["destination_station"],
            "route": route_data,
            "cached": True
        }
    except Exception as e:
        print(f"Error fetching from Supabase: {e}")
        return None

@app.route('/api/train/<train_number>', methods=['GET'])
def get_train_data(train_number):
    if not (train_number.isdigit() and len(train_number) == 5):
        return jsonify({
            "success": False,
            "error": "Invalid train number. Must be exactly 5 digits.",
            "example": "12345"
        }), 400

    # 1. Try fetching from Supabase
    cached_result = get_from_supabase(train_number)
    if cached_result:
        return jsonify(cached_result), 200

    # 2. If not in DB, scrape from IndiaRailInfo
    result = scrape_train_data(train_number)
    
    # 3. Save to Supabase if scraping was successful
    if result.get("success"):
        save_to_supabase(result)
        
    return jsonify(result), 200 if result.get("success") else 500

@app.route('/api/availability', methods=['GET'])
def get_availability():
    train_no = request.args.get('train_no')
    from_stn = request.args.get('from')
    to_stn = request.args.get('to')
    date = request.args.get('date')
    travel_class = request.args.get('class', 'SL')
    quota = request.args.get('quota', 'GN')

    if not all([train_no, from_stn, to_stn, date]):
        return jsonify({
            "success": False,
            "error": "Missing required query parameters: train_no, from, to, date"
        }), 400

    try:
        from availability_scraper.parsers.confirmtkt import ConfirmTktParser
        result = ConfirmTktParser.get_availability(
            train_no, from_stn, to_stn, date, travel_class, quota
        )
        return jsonify(result.to_dict()), 200 if result.success else 500
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.errorhandler(Exception)
def handle_global_exception(e):
    response = jsonify({
        "success": False,
        "error": f"Server Error: {str(e)}"
    })
    # Add CORS headers manually to guarantee browser compatibility on errors
    response.headers.add("Access-Control-Allow-Origin", "*")
    response.headers.add("Access-Control-Allow-Headers", "*")
    response.headers.add("Access-Control-Allow-Methods", "*")
    return response, 500

@app.route('/')
def serve_index():
    return app.send_static_file('index.html')

@app.route('/<path:path>')
def serve_static(path):
    return app.send_static_file(path)

if __name__ == '__main__':
    app.run(debug=True)

