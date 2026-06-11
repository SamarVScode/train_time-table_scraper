from flask import Flask, request, jsonify, render_template_string
import time

app = Flask(__name__)

# ==========================================
# 1. LOCAL CACHE / SCRAED IRI QUOTA DICTIONARY
# ==========================================
# Simulating the static quota configurations scraped from India Rail Info
STATIC_QUOTA_MAPS = {
    "12616": [ # GT Express
        {"stationCode": "NDLS", "quotaZone": "GNWL"},
        {"stationCode": "ALJN", "quotaZone": "GNWL"},
        {"stationCode": "CNB",  "quotaZone": "RLWL"},
        {"stationCode": "BPL",  "quotaZone": "RLWL"},
        {"stationCode": "MAS",  "quotaZone": "RLWL"}
    ],
    "12533": [ # Pushpak Express
        {"stationCode": "LKO",  "quotaZone": "GNWL"},
        {"stationCode": "CNB",  "quotaZone": "GNWL"},
        {"stationCode": "BPL",  "quotaZone": "RLWL"}
    ]
}

# ==========================================
# 2. MOCK LIVE THIRD-PARTY APIS (RapidAPI/eRail)
# ==========================================
def mock_trains_between_stations(source, destination):
    """Simulates discovering direct trains."""
    if source == "CNB" and destination == "MAS":
        return [{"number": "12616", "name": "GT Express"}]
    if source == "LKO" and destination == "BPL":
        return [{"number": "12533", "name": "Pushpak Express"}]
    return [] # Returns empty to simulate no direct trains (triggers chaining)

def mock_live_availability(train_number, source, destination):
    """Simulates live seat checking."""
    # Scenario A: Direct Kanpur to Chennai is Waitlisted
    if train_number == "12616" and source == "CNB" and destination == "MAS":
        return {"status": "WAITLIST", "seats": 0, "quota": "RLWL"}
    # Loophole A: Booking from Aligarh (GNWL zone) to Chennai has seats!
    if train_number == "12616" and source == "ALJN" and destination == "MAS":
        return {"status": "AVAILABLE", "seats": 14, "quota": "GNWL"}
        
    # Scenario B: Chaining Leg 1 (Lucknow to Bhopal) is directly available
    if train_number == "12533" and source == "LKO" and destination == "BPL":
        return {"status": "AVAILABLE", "seats": 42, "quota": "GNWL"}
        
    # Scenario C: Chaining Leg 2 (Bhopal to Chennai) is blocked direct
    if train_number == "12616" and source == "BPL" and destination == "MAS":
        return {"status": "WAITLIST", "seats": 0, "quota": "PQWL"}
    # Loophole C: Booking Leg 2 from New Delhi instead unlocks GNWL seats
    if train_number == "12616" and source == "NDLS" and destination == "MAS":
        return {"status": "AVAILABLE", "seats": 8, "quota": "GNWL"}

    return {"status": "WAITLIST", "seats": 0, "quota": "UNKNOWN"}

def mock_graph_chain_paths(source, destination):
    """Simulates network graph path planning up to a 4-leg threshold."""
    if source == "LKO" and destination == "MAS":
        return [
            {
                "legs": [
                    {"from": "LKO", "to": "BPL", "trainNumber": "12533", "trainName": "Pushpak Express"},
                    {"from": "BPL", "to": "MAS", "trainNumber": "12616", "trainName": "GT Express"}
                ]
            }
        ]
    return []

# ==========================================
# 3. CORE PROCESSING LOGIC (The Smart Engine)
# ==========================================
def evaluate_single_train_gnwl(source, destination, train_number, train_name):
    """Checks direct availability, falls back to GNWL optimization if waitlisted."""
    direct = mock_live_availability(train_number, source, destination)
    if direct["status"] == "AVAILABLE":
        return {
            "strategy": "DIRECT",
            "trainNumber": train_number,
            "trainName": train_name,
            "bookingStation": source,
            "boardingStation": source,
            "seats": direct["seats"]
        }

    # Direct failed, lookup local pre-scraped IRI quota map
    quota_map = STATIC_QUOTA_MAPS.get(train_number)
    if not quota_map:
        return {"strategy": "FAILED"}

    # Scan backwards to find closest GNWL station
    optimal_gnwl_station = None
    for stop in quota_map:
        if stop["quotaZone"] == "GNWL":
            optimal_gnwl_station = stop["stationCode"]
        if stop["stationCode"] == source:
            break

    if optimal_gnwl_station and optimal_gnwl_station != source:
        # Re-check live API using the loophole station
        fallback = mock_live_availability(train_number, optimal_gnwl_station, destination)
        if fallback["status"] == "AVAILABLE":
            return {
                "strategy": "GNWL_OPTIMIZED",
                "trainNumber": train_number,
                "trainName": train_name,
                "bookingStation": optimal_gnwl_station,
                "boardingStation": source,
                "seats": fallback["seats"]
            }

    return {"strategy": "FAILED"}

# ==========================================
# 4. FLASK ROUTE HANDLERS
# ==========================================
@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/search', methods=['POST'])
def search():
    data = request.json
    source = data.get("source", "").upper().strip()
    destination = data.get("destination", "").upper().strip()
    
    # STAGE 1: Check Direct Trains
    direct_trains = mock_trains_between_stations(source, destination)
    direct_options = []
    
    for t in direct_trains:
        res = evaluate_single_train_gnwl(source, destination, t["number"], t["name"])
        if res["strategy"] != "FAILED":
            direct_options.append(res)
            
    if direct_options:
        return jsonify({"type": "SINGLE_TRAIN_OPTIONS", "data": direct_options})

    # STAGE 2: Direct failed entirely, initialize Train Chaining Matrix
    potential_chains = mock_graph_chain_paths(source, destination)
    valid_chains = []
    
    for chain in potential_chains:
        is_chain_viable = True
        validated_legs = []
        
        for leg in chain["legs"]:
            # Evaluate each individual leg using the exact nested GNWL algorithm
            leg_res = evaluate_single_train_gnwl(leg["from"], leg["to"], leg["trainNumber"], leg["trainName"])
            if leg_res["strategy"] == "FAILED":
                is_chain_viable = False
                break
            validated_legs.append(leg_res)
            
        if is_chain_viable:
            valid_chains.append({
                "totalLegs": len(validated_legs),
                "legs": validated_legs
            })

    if valid_chains:
        return jsonify({"type": "CHAINED_OPTIONS", "data": valid_chains})
        
    return jsonify({"type": "SOLD_OUT", "message": "All search layers and chaining limits exhausted. No seats found."})


# ==========================================
# 5. INBUILT TESTING HTML INTERFACE (Tailwind)
# ==========================================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Smart Train Availability Engine (STAE)</title>
    <script src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4"></script>
</head>
<body class="bg-gray-900 text-gray-100 min-h-screen">
    <div class="container mx-auto px-4 py-8 max-w-5xl">
        
        <!-- Header -->
        <header class="mb-8 border-b border-gray-800 pb-4">
            <h1 class="text-3xl font-extrabold text-blue-400">STAE Sandbox</h1>
            <p class="text-gray-400 text-sm mt-1">Testing Suite: GNWL Boundary Loopholes & Multi-Leg Chaining</p>
        </header>

        <!-- Test Presets Sandbox Bar -->
        <div class="bg-gray-800 p-4 rounded-xl mb-6 border border-gray-700">
            <span class="text-sm font-semibold text-gray-400 uppercase tracking-wider block mb-2">Quick Test Scenarios:</span>
            <div class="flex flex-wrap gap-2">
                <button onclick="applyPreset('LKO', 'BPL')" class="bg-gray-700 hover:bg-gray-600 text-xs font-medium py-2 px-3 rounded-lg transition">
                    🟢 Case 1: Direct Available (LKO ➔ BPL)
                </button>
                <button onclick="applyPreset('CNB', 'MAS')" class="bg-gray-700 hover:bg-gray-600 text-xs font-medium py-2 px-3 rounded-lg transition">
                    🔵 Case 2: GNWL Loophole (CNB ➔ MAS)
                </button>
                <button onclick="applyPreset('LKO', 'MAS')" class="bg-gray-700 hover:bg-gray-600 text-xs font-medium py-2 px-3 rounded-lg transition">
                    🟣 Case 3: 4-Depth Chaining + GNWL (LKO ➔ MAS)
                </button>
            </div>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
            <!-- Left Panel: Input Fields -->
            <div class="bg-gray-800 p-6 rounded-2xl border border-gray-700 h-fit shadow-xl">
                <h2 class="text-lg font-bold mb-4 text-gray-200">Search Configuration</h2>
                <div class="space-y-4">
                    <div>
                        <label class="block text-xs font-semibold uppercase tracking-wider text-gray-400 mb-1">Source Station</label>
                        <input type="text" id="source" placeholder="e.g. CNB" class="w-full bg-gray-900 border border-gray-700 rounded-xl px-4 py-2.5 text-white font-mono focus:outline-none focus:border-blue-500 uppercase">
                    </div>
                    <div>
                        <label class="block text-xs font-semibold uppercase tracking-wider text-gray-400 mb-1">Destination Station</label>
                        <input type="text" id="destination" placeholder="e.g. MAS" class="w-full bg-gray-900 border border-gray-700 rounded-xl px-4 py-2.5 text-white font-mono focus:outline-none focus:border-blue-500 uppercase">
                    </div>
                    <div>
                        <label class="block text-xs font-semibold uppercase tracking-wider text-gray-400 mb-1">Travel Date</label>
                        <input type="date" value="2026-06-25" id="date" class="w-full bg-gray-900 border border-gray-700 rounded-xl px-4 py-2.5 text-white focus:outline-none focus:border-blue-500">
                    </div>
                    <button onclick="runEngineSearch()" class="w-full bg-blue-600 hover:bg-blue-500 text-white font-bold py-3 px-4 rounded-xl transition shadow-lg shadow-blue-900/30 mt-2">
                        Execute Search Engine
                    </button>
                </div>
            </div>

            <!-- Right Panel: Dynamic Render View -->
            <div class="md:col-span-2">
                <h2 class="text-lg font-bold mb-4 text-gray-200">System Logs & Output</h2>
                <div id="outputContainer" class="space-y-4">
                    <div class="bg-gray-800/50 border border-dashed border-gray-700 rounded-2xl p-12 text-center text-gray-500">
                        Configure search input parameters or click a quick shortcut scenario preset to compute alternate routing models.
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        function applyPreset(src, dest) {
            document.getElementById('source').value = src;
            document.getElementById('destination').value = dest;
            runEngineSearch();
        }

        async function runEngineSearch() {
            const source = document.getElementById('source').value;
            const destination = document.getElementById('destination').value;
            const date = document.getElementById('date').value;
            const container = document.getElementById('outputContainer');

            if (!source || !destination) {
                alert("Please declare both target station variables.");
                return;
            }

            container.innerHTML = `<div class="bg-gray-800 p-8 rounded-2xl text-center border border-gray-700">
                <div class="animate-pulse text-blue-400 font-medium">Interrogating live API endpoints & parsing static quota topologies...</div>
            </div>`;

            try {
                const response = await fetch('/api/search', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ source, destination, date })
                });
                const result = await response.json();
                renderResults(result);
            } catch (err) {
                container.innerHTML = `<div class="bg-red-950/40 border border-red-800 p-4 rounded-xl text-red-400">Engine execution faulted connecting to backend controller.</div>`;
            }
        }

        function renderResults(result) {
            const container = document.getElementById('outputContainer');
            container.innerHTML = "";

            if (result.type === "SOLD_OUT") {
                container.innerHTML = `<div class="bg-red-950/30 border border-red-900/50 text-red-300 p-6 rounded-2xl">
                    <div class="font-bold text-lg mb-1">❌ System Limit Exhausted</div>
                    <p class="text-sm text-red-400/80">${result.message}</p>
                </div>`;
                return;
            }

            if (result.type === "SINGLE_TRAIN_OPTIONS") {
                result.data.forEach(item => {
                    if (item.strategy === "DIRECT") {
                        container.innerHTML += `
                            <div class="bg-emerald-950/30 border border-emerald-800/50 p-5 rounded-2xl shadow-lg">
                                <div class="flex justify-between items-start mb-2">
                                    <div>
                                        <span class="bg-emerald-800 text-emerald-100 text-xs px-2.5 py-1 rounded-md font-bold mr-2 uppercase tracking-wide">Direct Allocation</span>
                                        <h3 class="text-lg font-bold text-emerald-300 inline-block">${item.trainName} (${item.trainNumber})</h3>
                                    </div>
                                    <span class="text-emerald-400 font-extrabold text-xl">${item.seats} Seats</span>
                                </div>
                                <p class="text-gray-400 text-sm">Direct path validation passed. Standard inventory allocation available from source terminal.</p>
                            </div>`;
                    } else if (item.strategy === "GNWL_OPTIMIZED") {
                        container.innerHTML += `
                            <div class="bg-blue-950/40 border border-blue-900/60 p-5 rounded-2xl shadow-lg border-l-4 border-l-blue-500">
                                <div class="flex justify-between items-start mb-3">
                                    <div>
                                        <span class="bg-blue-800 text-blue-100 text-xs px-2.5 py-1 rounded-md font-bold mr-2 uppercase tracking-wide">💡 GNWL Loophole Detected</span>
                                        <h3 class="text-lg font-bold text-blue-300 inline-block">${item.trainName} (${item.trainNumber})</h3>
                                    </div>
                                    <span class="text-blue-400 font-extrabold text-xl">${item.seats} Seats</span>
                                </div>
                                <div class="bg-gray-900/80 p-4 rounded-xl border border-gray-800 text-sm space-y-1">
                                    <p class="text-gray-300"><strong class="text-amber-400">Checkout Protocol:</strong> Purchase ticket originating from <span class="bg-gray-800 px-1.5 py-0.5 rounded text-white font-mono font-bold">${item.bookingStation}</span>.</p>
                                    <p class="text-gray-300"><strong class="text-amber-400">Boarding Lock:</strong> Modify passenger boarding execution point to <span class="bg-gray-800 px-1.5 py-0.5 rounded text-white font-mono font-bold">${item.boardingStation}</span>.</p>
                                </div>
                            </div>`;
                    }
                });
            }

            if (result.type === "CHAINED_OPTIONS") {
                result.data.forEach((chain, index) => {
                    let legsHTML = "";
                    chain.legs.forEach((leg, i) => {
                        let strategyBadge = leg.strategy === 'DIRECT' 
                            ? `<span class="bg-emerald-900/60 text-emerald-300 text-[10px] px-2 py-0.5 rounded font-bold uppercase">Direct</span>`
                            : `<span class="bg-blue-900/60 text-blue-300 text-[10px] px-2 py-0.5 rounded font-bold uppercase">💡 GNWL Optimized</span>`;
                        
                        let instructions = leg.strategy === 'GNWL_OPTIMIZED'
                            ? `<div class="mt-2 text-xs text-blue-400 bg-blue-950/30 p-2 rounded border border-blue-900/40">Loophole Action: Book from <strong>${leg.bookingStation}</strong>, Board at <strong>${leg.boardingStation}</strong></div>`
                            : `<div class="mt-2 text-xs text-emerald-400 bg-emerald-950/20 p-2 rounded border border-emerald-900/30">Action: Book standard route parameters normally.</div>`;

                        legsHTML += `
                            <div class="relative pl-6 border-l border-gray-700 py-2">
                                <div class="absolute -left-[5px] top-4 w-2.5 h-2.5 rounded-full bg-purple-500"></div>
                                <div class="flex justify-between items-center">
                                    <div class="text-sm font-bold text-gray-200">Segment ${i+1}: ${leg.trainName} <span class="font-mono font-normal text-gray-400">(${leg.trainNumber})</span></div>
                                    <div class="flex items-center gap-2">
                                        ${strategyBadge}
                                        <span class="text-xs font-bold text-purple-300">${leg.seats} Seats</span>
                                    </div>
                                </div>
                                <p class="text-xs text-gray-400 mt-0.5">Travel vector: ${leg.boardingStation} ➔ Final Leg Stop</p>
                                ${instructions}
                            </div>`;
                        
                        if(i < chain.legs.length - 1) {
                            legsHTML += `
                            <div class="my-1 py-1 text-center bg-gray-900/40 border border-dashed border-gray-800 text-[11px] font-bold text-amber-400 tracking-wider rounded-lg">
                                🔄 OPTIMAL INTERMEDIATE JUNCTION BUFFER LAYOVER
                            </div>`;
                        }
                    });

                    container.innerHTML += `
                        <div class="bg-purple-950/20 border border-purple-900/40 p-5 rounded-2xl shadow-lg">
                            <div class="text-xs uppercase font-extrabold tracking-wider text-purple-400 mb-3 block">
                                🗺️ Alternative Multi-Leg Chain Vector Topology (${chain.totalLegs} Segment Path)
                            </div>
                            <div class="space-y-2">${legsHTML}</div>
                        </div>`;
                });
            }
        }
    </script>
</body>
</html>
"""

if __name__ == '__main__':
    app.run(debug=True)
