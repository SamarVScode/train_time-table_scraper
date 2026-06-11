from flask import Flask, jsonify, request
from flask_cors import CORS
import re
import requests
from bs4 import BeautifulSoup

app = Flask(__name__)
CORS(app)

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
    scraperapi_key = '2489929e94aa0f1851699927d4155daf'
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
