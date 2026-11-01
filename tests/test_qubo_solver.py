import unittest
from qubo_solver import build_qubo, solve_exact, decode

class QuboFleetTests(unittest.TestCase):
    def test_exact_solver_assigns_each_vehicle_to_unique_station(self):
        vehicles = [{"id":"EV-1", "name":"Vehicle 1"}, {"id":"EV-2", "name":"Vehicle 2"}]
        candidates = [
            [{"station_id":"S1", "station_name":"Station 1", "score":10},
             {"station_id":"S2", "station_name":"Station 2", "score":12}],
            [{"station_id":"S1", "station_name":"Station 1", "score":9},
             {"station_id":"S2", "station_name":"Station 2", "score":11}],
        ]
        model = build_qubo(vehicles, candidates)
        bits, _ = solve_exact(model)
        assignments = decode(model, bits, vehicles)
        self.assertEqual(len(assignments), 2)
        self.assertTrue(all(a["status"] == "Feasible" for a in assignments))
        self.assertEqual(len({a["station_id"] for a in assignments}), 2)

if __name__ == "__main__":
    unittest.main()
