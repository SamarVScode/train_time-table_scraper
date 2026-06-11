from flask import Flask, jsonify, request, render_template_string
from flask_cors import CORS
import re
import requests
from bs4 import BeautifulSoup

app = Flask(__name__)
CORS(app) 

def clean_url(href):
    if not href: return ""
    if href.startswith('http://') or href.startswith('https://'): return href
    if href.startswith('//'): return f"https:{href}"
    prefix = "" if href.startswith('/') else "/"
    return f"https://indiarailinfo.com{prefix}{href}"

def live_scrape_app_json(train_number):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    search_url = f"https://indiarailinfo.com/blog?q={train_number}"
    try:
        res = requests.get(search_url, headers=headers, timeout=12)
        soup_search = BeautifulSoup(res.text, 'html.parser')
        timetable_url = None
        train_name = "Unknown Train"
        
        # FIX: Corrected regex string closure!
        iri_pattern = re.compile(rf"train/.*-{train_number}/\d+")
        
        for link in soup_search.find_all('a', href=True):
            if iri_pattern.search(link['href']):
                timetable_url = clean_url(link['href'])
                if "/" in link.text:
                    train_name = link.text.strip().split("/", 1)[1].strip()
                else:
                    train_name = link.text.strip()
                break
                
        if not timetable_url:
            return {"success": False, "error": f"Train {train_number} timeline link could not be parsed."}

        res_table = requests.get(timetable_url, headers=headers, timeout=12)
        soup_table = BeautifulSoup(res_table.text, 'html.parser')
        
        route_data = []
        rows = soup_table.find_all('div', class_='mrtbrow')
        for idx, row in enumerate(rows, start=1):
            cols = row.find_all('div')
            if len(cols) >= 10:
                stn_div = cols[1].find('a')
                stn_name = stn_div.text.strip() if stn_div else "Unknown"
                stn_code_span = cols[1].find('span')
                stn_code = stn_code_span.text.strip().replace('(','').replace(')','') if stn_code_span else ""
                
                arr = cols[2].text.strip()
                dep = cols[3].text.strip()
                dist = cols[6].text.strip()
                
                quota_span = cols[9].find('span')
                quota = quota_span.text.strip() if quota_span else "GN"
                
                route_data.append({
                    "stop": idx,
                    "name": stn_name,
                    "code": stn_code,
                    "arr": arr,
                    "dep": dep,
                    "distance_covered": dist,
                    "quota": quota
                })

        if not route_data:
            return {"success": False, "error": "Table parsed, but no route rows were found."}

        return {
            "success": True,
            "train": train_number,
            "name": train_name,
            "total_stops": len(route_data),
            "route": route_data
        }

    except Exception as e:
        return {"success": False, "error": f"Scraping Error: {str(e)}"}

@app.route('/api/train/<train_number>', methods=['GET'])
def get_train_data(train_number):
    if len(train_number) == 5 and train_number.isdigit():
        result = live_scrape_app_json(train_number)
        return jsonify(result)
    return jsonify({"success": False, "error": "Invalid Train Number format. Must be 5 digits."}), 400

@app.route('/', methods=['GET'])
def home():
    return render_template_string(HTML_INTERFACE)


HTML_INTERFACE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>IndiaRailInfo Scraper | Data Flow Test</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-900 text-gray-100 min-h-screen p-6 font-sans">
    <div class="max-w-5xl mx-auto">
        <header class="mb-8 text-center">
            <h1 class="text-3xl font-extrabold text-blue-400">Route & Quota Engine</h1>
            <p class="text-gray-400 mt-2 text-sm">Testing the live data flow from the Python scraping API.</p>
        </header>

        <div class="bg-gray-800 p-6 rounded-2xl border border-gray-700 shadow-xl max-w-md mx-auto mb-8">
            <label class="block text-xs font-semibold uppercase tracking-wider text-gray-400 mb-2">Enter Train Number</label>
            <div class="flex gap-3">
                <input type="text" id="trainInput" placeholder="e.g., 12533" maxlength="5" 
                       class="w-full bg-gray-900 border border-gray-600 rounded-xl px-4 py-2 text-white font-mono focus:outline-none focus:border-blue-500">
                <button onclick="fetchTrainData()" class="bg-blue-600 hover:bg-blue-500 text-white font-bold py-2 px-6 rounded-xl transition shadow-lg shadow-blue-900/30">
                    Search
                </button>
            </div>
            <p id="statusMsg" class="text-xs mt-3 text-amber-400 hidden animate-pulse">Initializing scraper engine... (this takes a few seconds)</p>
        </div>

        <div id="outputContainer" class="hidden bg-gray-800 rounded-2xl border border-gray-700 shadow-xl overflow-hidden">
            <div class="bg-gray-900/50 p-6 border-b border-gray-700 flex justify-between items-center">
                <div>
                    <h2 id="trainName" class="text-2xl font-bold text-gray-100">Train Name</h2>
                    <p id="trainDetails" class="text-sm text-gray-400 mt-1">Train: ----- | Total Stops: --</p>
                </div>
                <div class="bg-emerald-900/40 border border-emerald-800 text-emerald-400 px-4 py-2 rounded-lg text-sm font-bold">Success: 200 OK</div>
            </div>
            <div class="overflow-x-auto">
                <table class="w-full text-left text-sm whitespace-nowrap">
                    <thead class="bg-gray-900/80 text-gray-400 uppercase text-xs tracking-wider border-b border-gray-700">
                        <tr>
                            <th class="px-6 py-4">#</th>
                            <th class="px-6 py-4">Station</th>
                            <th class="px-6 py-4">Arr / Dep</th>
                            <th class="px-6 py-4">Distance</th>
                            <th class="px-6 py-4">Quota Zone</th>
                        </tr>
                    </thead>
                    <tbody id="tableBody" class="divide-y divide-gray-700/50"></tbody>
                </table>
            </div>
        </div>

        <div id="errorContainer" class="hidden bg-red-950/30 border border-red-900/50 text-red-300 p-6 rounded-2xl max-w-2xl mx-auto mt-6">
            <div class="font-bold text-lg mb-1">❌ Pipeline Error</div>
            <p id="errorText" class="text-sm text-red-400/80"></p>
        </div>
    </div>

    <script>
        async function fetchTrainData() {
            const trainNum = document.getElementById('trainInput').value.trim();
            const statusMsg = document.getElementById('statusMsg');
            const output = document.getElementById('outputContainer');
            const errBox = document.getElementById('errorContainer');
            const errText = document.getElementById('errorText');

            if (trainNum.length !== 5 || isNaN(trainNum)) {
                alert("Please enter a valid 5-digit train number.");
                return;
            }

            output.classList.add('hidden');
            errBox.classList.add('hidden');
            statusMsg.classList.remove('hidden');

            try {
                const response = await fetch('/api/train/' + trainNum);
                const data = await response.json();
                statusMsg.classList.add('hidden');

                if (data.success) {
                    document.getElementById('trainName').innerText = data.name;
                    document.getElementById('trainDetails').innerText = 'Train: ' + data.train + ' | Total Stops: ' + data.total_stops;
                    const tbody = document.getElementById('tableBody');
                    tbody.innerHTML = ''; 

                    data.route.forEach(stop => {
                        let quotaBadge = '<span class="text-gray-500 text-xs">' + stop.quota + '</span>';
                        if (stop.quota.includes('GN')) {
                            quotaBadge = '<span class="bg-blue-900/50 text-blue-300 border border-blue-800 px-2 py-1 rounded text-xs font-bold">GNWL</span>';
                        } else if (stop.quota.includes('RL')) {
                            quotaBadge = '<span class="bg-purple-900/50 text-purple-300 border border-purple-800 px-2 py-1 rounded text-xs font-bold">RLWL</span>';
                        } else if (stop.quota.includes('PQ')) {
                            quotaBadge = '<span class="bg-amber-900/50 text-amber-300 border border-amber-800 px-2 py-1 rounded text-xs font-bold">PQWL</span>';
                        }

                        tbody.innerHTML += `
                            <tr class="hover:bg-gray-800/50 transition">
                                <td class="px-6 py-4 text-gray-500">` + stop.stop + `</td>
                                <td class="px-6 py-4 font-medium text-gray-200">` + stop.name + ` <span class="text-gray-500 font-mono text-xs">(` + stop.code + `)</span></td>
                                <td class="px-6 py-4 text-gray-300">` + stop.arr + ` / ` + stop.dep + `</td>
                                <td class="px-6 py-4 text-gray-300">` + stop.distance_covered + `</td>
                                <td class="px-6 py-4">` + quotaBadge + `</td>
                            </tr>`;
                    });
                    output.classList.remove('hidden');
                } else {
                    errText.innerText = data.error;
                    errBox.classList.remove('hidden');
                }
            } catch (error) {
                statusMsg.classList.add('hidden');
                errText.innerText = "Network execution failed. Check browser inspection console network tab.";
                errBox.classList.remove('hidden');
            }
        }
    </script>
</body>
</html>
"""
