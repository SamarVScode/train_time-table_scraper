from flask import Flask, jsonify, request
from flask_cors import CORS
import re
import requests
from bs4 import BeautifulSoup

app = Flask(__name__)
CORS(app)

def clean_url(href, base="https://indiarailinfo.com"):
    """Convert relative URLs to absolute URLs"""
    if not href:
        return ""
    if href.startswith(('http://', 'https://')):
        return href
    if href.startswith('//'):
        return f"https:{href}"
    prefix = "" if href.startswith('/') else "/"
    return f"{base}{prefix}{href}"

def scrape_train_data(train_number):
    """Scrape train timetable data from IndiaRailInfo and return as dict"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    search_url = f"https://indiarailinfo.com/blog?q={train_number}"

    try:
        # Step 1: Search for train to get timetable URL
        res = requests.get(search_url, headers=headers, timeout=15)
        res.raise_for_status()
        soup_search = BeautifulSoup(res.text, 'html.parser')

        timetable_url = None
        train_name = "Unknown Train"
        # FIX: The original regex was rf"/train/.*-{re.escape(train_number)}/\d+"
        # Sometimes train URLs don't have a hyphen right before the number (e.g. /train/12417/1149 or /train/12417-name/1149).
        # We relax the pattern to find /train/, followed by anything, then the train number, and then possibly a slash.
        iri_pattern = re.compile(rf"/train/.*{re.escape(train_number)}.*")

        for link in soup_search.find_all('a', href=True):
            href = link['href']
            if iri_pattern.search(href):
                timetable_url = clean_url(href)
                text = link.get_text(strip=True)
                train_name = text.split("/", 1)[1].strip() if "/" in text else text
                break

        if not timetable_url:
            return {
                "success": False,
                "error": f"Train {train_number} not found on IndiaRailInfo",
                "train_number": train_number
            }

        # Step 2: Scrape timetable page
        timetable_res = requests.get(timetable_url, headers=headers, timeout=15)
        timetable_res.raise_for_status()
        soup_table = BeautifulSoup(timetable_res.text, 'html.parser')

        table_container = soup_table.find('div', class_='newschtable')
        if not table_container:
            return {
                "success": False,
                "error": "Could not parse timetable. Website layout may have changed.",
                "train_number": train_number
            }

        # Parse station rows
        rows = table_container.find_all('div', recursive=False)
        route_data = []
        current_quota = "GN"
        current_leg = "Origin"

        for row in rows:
            cols = row.find_all('div', recursive=False)

            # Main station rows
            if len(cols) >= 18:
                stop_num_text = cols[0].get_text(strip=True)
                if stop_num_text == "#" or not stop_num_text:
                    continue

                station_code = cols[2].get_text(strip=True)
                station_name = cols[3].get_text(strip=True)

                # Check quota updates
                note_col = cols[5]
                if note_col.has_attr('title'):
                    title = note_col['title'].lower()
                    if "remote location quota" in title:
                        current_quota = "RL"
                        current_leg = station_name
                    elif "pooled quota" in title:
                        current_quota = "PQ"
                        current_leg = station_name

                # Extract official distance
                km_col = cols[13]
                official_dist = km_col.get_text(strip=True)
                span = km_col.find('span')
                if span and span.has_attr('title') and "Official Km:" in span['title']:
                    official_dist = span['title'].split("Official Km:")[-1].strip()

                station_entry = {
                    "stop": int(stop_num_text) if stop_num_text.isdigit() else stop_num_text,
                    "code": station_code,
                    "name": station_name,
                    "arrival": cols[6].get_text(strip=True) or "-",
                    "departure": cols[8].get_text(strip=True) or "-",
                    "halt_time": cols[10].get_text(strip=True) or "-",
                    "platform": cols[11].get_text(strip=True) or "-",
                    "day": cols[12].get_text(strip=True) or "1",
                    "distance_km": f"{official_dist} km" if official_dist else "-",
                    "quota": current_quota,
                    "leg_from": current_leg
                }
                route_data.append(station_entry)

            # Intermediate gap rows
            elif 'intrmdtstn' in row.get('class', []):
                if len(cols) >= 5 and route_data:
                    stops_text = cols[0].get_text(strip=True)
                    time_text = cols[2].get_text(strip=True)
                    dist_text = cols[4].get_text(strip=True)
                    stop_count = stops_text.split()[0] if ' ' in stops_text else "0"

                    route_data[-1]["next_segment"] = {
                        "intermediate_stops": int(stop_count) if stop_count.isdigit() else 0,
                        "travel_time": time_text or "-",
                        "distance": f"{dist_text} km" if dist_text else "-"
                    }

        # Clean last station
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

@app.route('/api/train/<train_number>', methods=['GET'])
def get_train_data(train_number):
    if not (train_number.isdigit() and len(train_number) == 5):
        return jsonify({
            "success": False,
            "error": "Invalid train number. Must be exactly 5 digits.",
            "example": "12345"
        }), 400

    result = scrape_train_data(train_number)
    return jsonify(result), 200 if result.get("success") else 500

if __name__ == '__main__':
    app.run(debug=True)
