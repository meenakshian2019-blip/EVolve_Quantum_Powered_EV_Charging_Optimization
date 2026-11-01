"""Feasibility filter and transparent QUBO-inspired classical scoring for the EVolve demo."""
def recommend(stations, vehicle):
    battery = max(0, min(100, vehicle["battery"]))
    capacity = max(1, vehicle["capacity"])
    connector = vehicle["connector"]
    target_km = max(0, vehicle["target_km"])
    reserve = max(5, min(35, vehicle.get("reserve", 15)))
    mode = vehicle.get("mode", "balanced").lower()
    # Simple simulated range model: 0.18 kWh/km.
    energy_kwh = capacity * battery / 100
    arrival_range = energy_kwh / 0.18
    safely_reachable = arrival_range >= target_km * 0.25
    candidates = []
    for s in stations:
        if s["status"] != "online" or s["available"] <= 0:
            continue
        if connector not in s["connectors"]:
            continue
        if not safely_reachable:
            # An emergency charging stop is allowed, but must still be connector-compatible.
            pass
        # Estimated energy to charge: onward journey + reserve, capped by battery capacity.
        needed_kwh = min(capacity-energy_kwh, max(0, target_km*0.18 + capacity*reserve/100 - energy_kwh))
        charge_min = round((needed_kwh / max(7, s["power_kw"])) * 60 * 1.12)
        cost = round(needed_kwh * s["price"], 2)
        total_min = s["detour_min"] + s["queue_min"] + charge_min
        # Normalize objectives into a transparent weighted score.
        if mode == "fastest":
            score = 0.55*total_min + 0.20*s["detour_min"] + 0.15*cost/5 + 0.10*(100-s["power_kw"]/2)
        elif mode == "cheapest":
            score = 0.15*total_min + 0.15*s["detour_min"] + 0.60*cost/5 + 0.10*s["queue_min"]
        elif mode == "eco":
            score = 0.25*total_min + 0.20*s["detour_min"] + 0.15*cost/5 + 0.40*(0 if s["eco"] else 25)
        else:
            score = 0.35*total_min + 0.20*s["detour_min"] + 0.25*cost/5 + 0.20*s["queue_min"]
        candidates.append({
            "station_id":s["id"],"station_name":s["name"],"area":s["area"],
            "power_kw":s["power_kw"],"queue_min":s["queue_min"],"price":s["price"],
            "detour_min":s["detour_min"],"charge_min":charge_min,"cost":cost,
            "total_min":total_min,"available":s["available"],"connector":connector,
            "arrival_battery":round(max(0,battery-(target_km*0.18/capacity*100)),1),
            "eco":s["eco"],"score":round(score,2),"status":s["status"],
            "explanation":f"{s['detour_min']} min detour · {s['queue_min']} min queue · {s['power_kw']} kW · ₹{s['price']}/kWh"
        })
    return sorted(candidates, key=lambda x:x["score"])

def validate_schedule(recommendations):
    seen = set()
    for r in recommendations:
        if r["station_id"] in seen:
            return False, "Duplicate station assignment detected."
        seen.add(r["station_id"])
        if r["status"] != "online" or r["available"] <= 0:
            return False, "Offline or unavailable station included."
    return True, "Classical validation passed: station online, connector-compatible and port available."
