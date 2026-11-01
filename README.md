# EVolve — Smarter EV Charging with Quantum Optimization

A runnable web prototype based on the EVolve presentation. It demonstrates:
- Driver panel: compatible station discovery, battery/vehicle inputs, Fastest/Cheapest/Balanced/Eco modes, ranked explainable recommendations.
- Admin panel: station monitoring, port online/offline, tariff, queue and power interventions.
- Shared backend: admin changes immediately affect driver recommendations.
- Fleet demo: joint assignment across multiple simulated EVs.
- Classical safety validation and a QUBO-inspired scoring baseline.

**Important:** all stations, queues, tariffs, availability and route estimates are simulated. This prototype does not call live charger APIs or quantum hardware. The weighted scorer is a classical stand-in for the QUBO/QAOA optimization stage, so the UI can be demonstrated without quantum credentials. Replace `optimizer.py` with a QUBO/QAOA solver when ready.

## Run locally (Windows / VS Code)
1. Install Python 3.10 or newer.
2. Open this folder in VS Code.
3. In the terminal, create and activate a virtual environment:
   ```powershell
   py -m venv .venv
   .\\.venv\\Scripts\\Activate.ps1
   ```
   If activation is blocked, run `Set-ExecutionPolicy -Scope Process Bypass` and activate again.
4. Install dependencies:
   ```powershell
   pip install -r requirements.txt
   ```
5. Start the server:
   ```powershell
   python app.py
   ```
6. Open `http://127.0.0.1:5000`.

## Demo flow
1. In Driver, set battery, connector and trip distance; choose an optimization mode and click **Find best stop**.
2. Open Admin and mark a station offline, change its tariff/queue/power, then return to Driver and recalculate.
3. Use **Optimize fleet** to show joint allocation for multiple simulated EVs.
4. Explain that feasibility filtering and validation are classical safety gates; the current scorer is a transparent demo baseline, not a claim of running QAOA.

## Project structure
- `app.py` — Flask API and shared in-memory simulated state.
- `optimizer.py` — feasibility filter, weighted ranking and validation.
- `templates/index.html` — app layout.
- `static/style.css` — visual styling inspired by the provided reference.
- `static/app.js` — client-side interactions.

State resets when the server restarts. This is intentional for a lightweight demo. Do not use for real charging decisions.


## Step 1 fleet optimizer (QUBO)

The fleet endpoint now builds a binary QUBO assignment model. Each feasible vehicle/station pair is a binary variable. The objective combines normalized station recommendation scores with penalties for (1) assigning anything other than one station to a vehicle and (2) assigning the same station to multiple vehicles. Small demo instances are solved by exact classical enumeration; larger instances use a deterministic greedy QUBO fallback. The API returns the solver name, binary-variable count, QUBO energy/term count, and assignment validation.

This is a classical QUBO solver, not a claim that QAOA or quantum hardware has executed. Station/vehicle data remain simulated. Port-level, time-slot, power-limit and existing-session constraints are reserved for Step 2.

## Run the Step 1 solver test

With the project virtual environment active, run:

```powershell
python -m unittest discover -s tests -v
```

The test checks that the exact QUBO solver assigns each test vehicle and does not reuse a station.
