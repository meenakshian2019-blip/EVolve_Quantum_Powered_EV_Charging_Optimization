from flask import Flask, render_template, request, jsonify
from optimizer import recommend, validate_schedule
from datetime import datetime
from qubo_solver import build_qubo, solve_exact, solve_greedy, decode

app = Flask(__name__)

# All values are simulated for the prototype; no live charger network is queried.
STATIONS = [
    {"id":"KOC-01","name":"Marine Drive Charge Hub","area":"Kochi · Marine Drive","lat":9.9816,"lon":76.2762,"connectors":["CCS2","Type 2"],"ports":4,"available":3,"power_kw":150,"queue_min":8,"price":18.5,"detour_min":4,"status":"online","eco":True},
    {"id":"KOC-02","name":"Edappally Mobility Point","area":"Kochi · Edappally","lat":10.0261,"lon":76.3125,"connectors":["CCS2","CHAdeMO"],"ports":3,"available":1,"power_kw":60,"queue_min":19,"price":16.0,"detour_min":9,"status":"online","eco":False},
    {"id":"ALV-01","name":"Aluva Riverside Station","area":"Aluva · Riverside","lat":10.1076,"lon":76.3516,"connectors":["CCS2","Type 2"],"ports":3,"available":2,"power_kw":120,"queue_min":6,"price":17.2,"detour_min":7,"status":"online","eco":True},
    {"id":"TSR-01","name":"Thrissur Central Charge","area":"Thrissur · Round South","lat":10.5276,"lon":76.2144,"connectors":["CCS2","Type 2"],"ports":2,"available":2,"power_kw":90,"queue_min":3,"price":19.0,"detour_min":5,"status":"online","eco":False},
    {"id":"KOC-03","name":"Kakkanad Tech Park","area":"Kochi · Kakkanad","lat":10.0159,"lon":76.3419,"connectors":["Type 2"],"ports":2,"available":0,"power_kw":22,"queue_min":25,"price":14.0,"detour_min":11,"status":"online","eco":True},
]
EVENTS = [{"time":"Just now","title":"Simulation initialized","detail":"Station, queue and tariff values are simulated."}]
VEHICLES = [
    {"id":"EV-01","name":"Driver vehicle","battery":24,"capacity":60,"connector":"CCS2","range_km":110,"target_km":145},
    {"id":"EV-02","name":"Fleet vehicle A","battery":41,"capacity":72,"connector":"CCS2","range_km":180,"target_km":120},
    {"id":"EV-03","name":"Fleet vehicle B","battery":18,"capacity":52,"connector":"Type 2","range_km":75,"target_km":90},
]

def log(title, detail):
    EVENTS.insert(0, {"time":datetime.now().strftime("%H:%M:%S"),"title":title,"detail":detail})
    del EVENTS[12:]

@app.route("/")
def index():
    return render_template("index.html")

@app.get("/api/state")
def state():
    return jsonify({"stations":STATIONS,"vehicles":VEHICLES,"events":EVENTS,"simulation":True})

@app.post("/api/recommend")
def get_recommendation():
    data = request.get_json(force=True)
    vehicle = {
        "battery": int(data.get("battery", 24)),
        "capacity": int(data.get("capacity", 60)),
        "connector": data.get("connector", "CCS2"),
        "target_km": int(data.get("target_km", 145)),
        "reserve": int(data.get("reserve", 15)),
        "mode": data.get("mode", "balanced"),
    }
    results = recommend(STATIONS, vehicle)
    valid, reason = validate_schedule(results)
    log("Driver recommendation refreshed", f"{len(results)} feasible candidate(s); mode: {vehicle['mode']}.")
    return jsonify({"recommendations":results,"valid":valid,"validation":reason,"simulation":True,"optimizer":"Hybrid demo: classical feasibility filter + QUBO-inspired weighted scoring (quantum hardware not required)"})

@app.post("/api/admin/action")
def admin_action():
    data = request.get_json(force=True)
    sid = data.get("station_id")
    action = data.get("action")
    station = next((s for s in STATIONS if s["id"] == sid), None)
    if not station:
        return jsonify({"error":"Station not found"}), 404
    if action == "offline":
        station["status"] = "offline"
        station["available"] = 0
        detail = f"{station['name']} marked offline. Recommendations will exclude it."
    elif action == "online":
        station["status"] = "online"
        station["available"] = max(1, station["ports"] - 1)
        detail = f"{station['name']} restored. Availability is simulated."
    elif action == "tariff":
        station["price"] = round(float(data.get("price", station["price"])), 2)
        detail = f"Tariff updated to ₹{station['price']:.2f}/kWh at {station['name']}."
    elif action == "queue":
        station["queue_min"] = max(0, int(data.get("queue_min", station["queue_min"])))
        detail = f"Queue estimate updated to {station['queue_min']} minutes at {station['name']}."
    elif action == "power":
        station["power_kw"] = max(7, int(data.get("power_kw", station["power_kw"])))
        detail = f"Power limit updated to {station['power_kw']} kW at {station['name']}."
    else:
        return jsonify({"error":"Unknown action"}), 400
    log("Admin intervention", detail)
    return jsonify({"ok":True,"station":station,"impact":"Affected recommendations will be recalculated on the next driver request.","events":EVENTS})

@app.post("/api/optimize-fleet")
def optimize_fleet():
    # Build feasible vehicle-station candidates using the existing connector,
    # online-status and available-port filters in recommend().
    candidates_by_vehicle = []
    for v in VEHICLES:
        opts = recommend(STATIONS, {"battery":v["battery"], "capacity":v["capacity"],
            "connector":v["connector"], "target_km":v["target_km"],
            "reserve":15, "mode":"balanced"})
        candidates_by_vehicle.append(opts)

    model = build_qubo(VEHICLES, candidates_by_vehicle)
    solved = solve_exact(model)
    solver = "exact-classical-qubo"
    if solved is None:
        solved = solve_greedy(model, VEHICLES)
        solver = "classical-greedy-qubo-fallback"
    bits, qubo_energy = solved
    assignments = decode(model, bits, VEHICLES)
    assigned_ids = [a["station_id"] for a in assignments if a["station_id"]]
    unique_stations = len(assigned_ids) == len(set(assigned_ids))
    all_assigned = len(assigned_ids) == len(VEHICLES)
    valid = unique_stations and all_assigned and all(a["status"] == "Feasible" for a in assignments)
    log("Fleet QUBO optimization completed", f"{solver}; {model['num_variables']} binary variables; valid={valid}.")
    return jsonify({
        "assignments": assignments,
        "solver": solver,
        "qubo": {"binary_variables": model["num_variables"], "energy": round(float(qubo_energy), 6),
                 "one_hot_penalty": model["one_hot_penalty"], "station_exclusivity_penalty": model["station_penalty"],
                 "qubo_terms": len(model["Q"])},
        "validation": {"unique_stations": unique_stations, "all_vehicles_assigned": all_assigned, "valid": valid},
        "note": "QUBO objective optimized by exact classical enumeration for this small simulated fleet. QAOA is not being claimed as executed; all station and vehicle data are simulated.",
        "simulation": True
    })

if __name__ == "__main__":
    app.run(debug=True, port=5000)
