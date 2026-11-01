"""QUBO fleet assignment model with an exact classical solver for small demos.

Binary x[v,s] = 1 when vehicle v is assigned to candidate station s.
The objective minimizes normalized recommendation cost while enforcing:
  * exactly one station per vehicle (one-hot penalty)
  * at most one vehicle per station (pairwise exclusivity penalty)
"""
from itertools import product


def build_qubo(vehicles, candidates_by_vehicle, one_hot_penalty=100.0, station_penalty=100.0):
    variables = []
    for vi, vehicle in enumerate(vehicles):
        for candidate in candidates_by_vehicle[vi]:
            variables.append({"index": len(variables), "vehicle_index": vi,
                              "vehicle": vehicle["id"], "station_id": candidate["station_id"],
                              "station": candidate["station_name"], "score": float(candidate["score"]),
                              "candidate": candidate})
    # QUBO represented as upper-triangular dict: E(x)=sum Q[i,j]*x_i*x_j.
    Q = {}
    def add(i, j, value):
        key = (min(i, j), max(i, j))
        Q[key] = Q.get(key, 0.0) + value

    # Normalize score terms so penalties dominate the assignment objective.
    max_score = max([v["score"] for v in variables] or [1.0])
    min_score = min([v["score"] for v in variables] or [0.0])
    spread = max(1.0, max_score - min_score)
    for var in variables:
        add(var["index"], var["index"], (var["score"] - min_score) / spread)

    # A(1 - sum_s x_vs)^2: constant omitted, linear -A and pairwise +2A.
    for vi in range(len(vehicles)):
        ids = [v["index"] for v in variables if v["vehicle_index"] == vi]
        for i in ids:
            add(i, i, -one_hot_penalty)
        for p, i in enumerate(ids):
            for j in ids[p + 1:]:
                add(i, j, 2.0 * one_hot_penalty)

    # B * sum_{i<j at same station} x_i*x_j prevents station collisions.
    station_groups = {}
    for var in variables:
        station_groups.setdefault(var["station_id"], []).append(var["index"])
    for ids in station_groups.values():
        for p, i in enumerate(ids):
            for j in ids[p + 1:]:
                add(i, j, station_penalty)
    return {"variables": variables, "Q": Q, "constant": one_hot_penalty * len(vehicles),
            "one_hot_penalty": one_hot_penalty, "station_penalty": station_penalty, "num_variables": len(variables)}


def energy(bits, Q):
    return sum(value * bits[i] * bits[j] for (i, j), value in Q.items())


def solve_exact(model, max_variables=22):
    n = model["num_variables"]
    if n > max_variables:
        return None
    best_bits, best_energy = None, float("inf")
    # Exhaustive binary search is deterministic and suitable for the small demo fleet.
    for bits in product((0, 1), repeat=n):
        e = energy(bits, model["Q"])
        if e < best_energy:
            best_bits, best_energy = bits, e
    return best_bits, best_energy + model.get("constant", 0.0)


def solve_greedy(model, vehicles):
    chosen = [0] * model["num_variables"]
    used = set()
    for vi in range(len(vehicles)):
        options = [v for v in model["variables"] if v["vehicle_index"] == vi and v["station_id"] not in used]
        if options:
            pick = min(options, key=lambda x: x["score"])
            chosen[pick["index"]] = 1
            used.add(pick["station_id"])
    return tuple(chosen), energy(chosen, model["Q"]) + model.get("constant", 0.0)


def decode(model, bits, vehicles):
    selected = [v for v in model["variables"] if bits[v["index"]] == 1]
    by_vehicle = {i: [] for i in range(len(vehicles))}
    for var in selected:
        by_vehicle[var["vehicle_index"]].append(var)
    assignments = []
    for vi, vehicle in enumerate(vehicles):
        picks = by_vehicle[vi]
        if len(picks) == 1:
            c = picks[0]["candidate"]
            assignments.append({"vehicle": vehicle["id"], "vehicle_name": vehicle["name"],
                "station": c["station_name"], "station_id": c["station_id"],
                "score": c["score"], "status": "Feasible"})
        else:
            assignments.append({"vehicle": vehicle["id"], "vehicle_name": vehicle["name"],
                "station": "No unique feasible station", "station_id": None,
                "score": None, "status": "Needs fallback"})
    return assignments
