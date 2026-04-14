# 🧬 DNA Cluster: Team Execution Guide

Welcome to the distributed DNA comparison cluster! This guide will walk you through exactly how to set up your laptop, connect to the swarm, process a massive 3GB `.fna` file collectively, and test our fault-tolerance and scheduling controls.

---

## 🚀 Phase 1: Initial Setup (Everyone)

Everyone on the team (Sebas, Juanjo, Nico, Jhonny, David) needs to perform these steps on their own laptops.

### 1. Get the Code
Open your terminal and run:
```bash
git clone git@github.com:SebasChicaiza/adn-distribuido.git
cd adn-distribuido
```

### 2. Set Up the Python Environment
We need to isolate our dependencies.
```bash
python -m venv .venv

# On Linux/macOS:
source .venv/bin/activate
# On Windows:
# .venv\Scripts\activate

pip install -r requirements.txt
pip install -e .
```

### 3. ⚠️ CRITICAL: The 3GB DNA Files
For the distributed hashing and preprocessing to work correctly without transferring 3GB over the internet, **every node must have the exact same input files locally**.

1. Download the massive `a.fna` and `b.fna` files from our shared drive.
2. Create the input directory if it doesn't exist: `mkdir -p data/input`
3. Place them exactly here:
   - `adn-distribuido/data/input/a.fna`
   - `adn-distribuido/data/input/b.fna`

---

## 🌐 Phase 2: Connecting the Cluster

We use `ngrok` so our laptops can talk to each other over the public internet.

### 1. Configure your `.env` file
Copy the example file: `cp .env.example .env`

Now, edit your `.env` file. You **must** change `NODE_ID` to your specific name. 

```env
# CHANGE THIS TO YOUR NAME (e.g., node_juanjo, node_nico, node_jhonny, node_david, node_sebas)
NODE_ID=node_sebas  

# Use 'worker_standby' if you want to be a potential leader, or 'worker' for pure processing.
ROLE_MODE=worker_standby

# Set this to YOUR specific IP or ngrok URL.
# Sebas:  http://192.168.208.96:8001
# Juanjo: http://192.168.208.92:8001
# Nico:   http://192.168.210.44:8001
# Jhonny: http://192.168.210.40:8001
# David:  https://magnesium-slicer-exhume.ngrok-free.dev
PUBLIC_URL=http://192.168.208.96:8001

# DO NOT CHANGE THIS LINE.
CLUSTER_NODES=node_sebas,http://192.168.208.96:8001,100;node_juanjo,http://192.168.208.92:8001,90;node_nico,http://192.168.210.44:8001,80;node_jhonny,http://192.168.210.40:8001,70;node_david,https://magnesium-slicer-exhume.ngrok-free.dev,60

DATA_DIR=./data
INPUT_A_PATH=./data/input/a.fna
INPUT_B_PATH=./data/input/b.fna
LOG_LEVEL=INFO
```

### 2. Open Connectivity
- **Sebas, Juanjo, Nico, Jhonny:** Ensure you are on the university network and port 8001 is open.
- **David:** Expose port 8001 using ngrok:
  `ngrok http 8001 --domain=magnesium-slicer-exhume.ngrok-free.dev`

### 3. Start the Manager Node
Before starting, it is highly recommended to clean any old local state or test data so you start fresh:

**On Linux/macOS:**
```bash
rm -rf data/state/* data/work/* data/output/* data/normalized/*
```
**On Windows (PowerShell):**
```powershell
Remove-Item -Recurse -Force data\state\*, data\work\*, data\output\*, data\normalized\*
```

Once cleaned, go back to your main terminal (where your `.venv` is active) and start the system. **Everyone in the priority list should run `run_manager` to ensure failover works.**

```bash
python -m dna_cluster.cli.run_manager
```
Because of the `CLUSTER_NODES` config, **Sebas (Priority 100)** will automatically become the Leader. Everyone else will connect to Sebas, sync state, and wait for work.

---

## 💥 Phase 3: Running the 3GB Job & Chaos Testing

Once everyone is connected, **Sebas** (or whoever is currently the Leader) can open a 3rd terminal and orchestrate the cluster using `curl` commands.

### 1. Check the Cluster Status
See everyone's RAM, CPU, and connection status in real-time:
```bash
curl http://localhost:8001/api/v1/leader/control/status
```

### 2. Start the Massive 3GB Job
This tells the Leader to chunk the 3GB file and start handing out pieces to the swarm:
```bash
curl -X POST http://localhost:8001/api/v1/leader/job/create \
     -H "Content-Type: application/json" \
     -d '{"job_id": "massive_3gb_job"}'
```
*Watch your terminals! You will see chunks being downloaded, processed, and uploaded back to the Leader.*

### 3. Chaos Testing (Failover)
Let's see the Standby promotion in action.
1. Make sure the job is running.
2. **Sebas hits `CTRL+C`** on his `run_manager.py` terminal. Sebas is dead.
3. **Juanjo (Priority 90)** will notice Sebas's heartbeats stopped. After 45 seconds (lease timeout), Juanjo's terminal will log: `Promoted to LEADER! New term: 2`.
4. Nico, Jhonny, and David will automatically detect the new leader, reconnect to Juanjo's ngrok URL, and resume processing the 3GB file exactly where they left off!
