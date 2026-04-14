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

Now, edit your `.env` file. You **must** change `NODE_ID` to your specific name. If you are acting as a Standby (Juanjo, Nico, Jhonny, David), you must also set `PUBLIC_URL` to your personal ngrok domain.

```env
# CHANGE THIS TO YOUR NAME (e.g., node_juanjo, node_nico, node_jhonny, node_david, node_sebas)
NODE_ID=node_sebas  

ROLE_MODE=worker_standby

# If you are a standby, put YOUR ngrok URL here. If you are Sebas, put Sebas's URL.
PUBLIC_URL=https://kristy-vertebral-toilfully.ngrok-free.dev

# Do NOT change this line. This is the master map of the cluster.
CLUSTER_NODES=node_sebas,https://kristy-vertebral-toilfully.ngrok-free.dev,100;node_juanjo,https://juanjo.ngrok.app,90;node_nico,https://graves-angelfish-disclose.ngrok-free.dev,80;node_jhonny,https://item-overrun-glorified.ngrok-free.dev,70;node_david,https://magnesium-slicer-exhume.ngrok-free.dev,60

DATA_DIR=./data
INPUT_A_PATH=./data/input/a.fna
INPUT_B_PATH=./data/input/b.fna
LOG_LEVEL=INFO
```

### 2. Open your Ngrok Tunnel (Standbys & Leader)
In a **new, separate terminal**, run your specific ngrok command to expose port 8001 to the internet:

- **Sebas:** `ngrok http 8001 --domain=kristy-vertebral-toilfully.ngrok-free.dev`
- **Nico:** `ngrok http 8001 --domain=graves-angelfish-disclose.ngrok-free.dev`
- **Jhonny:** `ngrok http 8001 --domain=item-overrun-glorified.ngrok-free.dev`
- **David:** `ngrok http 8001 --domain=magnesium-slicer-exhume.ngrok-free.dev`
- **Juanjo:** `ngrok http 8001 --domain=juanjo.ngrok.app` *(Make sure this matches your actual reserved domain)*

### 3. Start the Manager Node (or Node Agent)
Before starting, it is highly recommended to clean any old local state or test data so you start fresh:

**On Linux/macOS:**
```bash
rm -rf data/state/* data/work/* data/output/* data/normalized/*
```
**On Windows (PowerShell):**
```powershell
Remove-Item -Recurse -Force data\state\*, data\work\*, data\output\*, data\normalized\*
```

Once cleaned, go back to your main terminal (where your `.venv` is active) and start the system:
```bash
# If you are Sebas (Leader) or a Standby (Juanjo):
python -m dna_cluster.cli.run_manager

# If you are strictly a Worker (Nico, Jhonny, David):
python -m dna_cluster.cli.run_node
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

### 3. Chaos Test A: Pin All Traffic to One Node
Want to benchmark Nico's laptop? You can tell the Leader to *only* give chunks to Nico:
```bash
curl -X POST http://localhost:8001/api/v1/leader/control/set_scheduler_mode \
     -H "Content-Type: application/json" \
     -d '{"mode": "pin_single_node", "pinned_node_id": "node_nico"}'
```
To return to normal balanced load:
```bash
curl -X POST http://localhost:8001/api/v1/leader/control/set_scheduler_mode \
     -H "Content-Type: application/json" \
     -d '{"mode": "balanced"}'
```

### 4. Chaos Test B: Kill a Worker (Stuck Chunk Requeue)
1. While the job is running, tell **David** to hit `CTRL+C` on his `run_manager.py` terminal.
2. Watch the Leader's logs. After 30-60 seconds, the Leader will realize David is dead.
3. The Leader will log `Chunk stuck on node node_david. Requeuing.`
4. The Leader will take the chunk David was working on and give it to Juanjo or Nico instead. The job survives!

### 5. Chaos Test C: Kill the Leader (Failover)
Let's see the Standby promotion in action.
1. Make sure the job is running.
2. **Sebas hits `CTRL+C`** on his `run_manager.py` terminal. Sebas is dead.
3. **Juanjo (Priority 90)** will notice Sebas's heartbeats stopped. After 15 seconds, Juanjo's terminal will log: `Promoted to LEADER! New term: 2`.
4. Nico, Jhonny, and David will automatically detect the new leader, reconnect to Juanjo's ngrok URL, and resume processing the 3GB file exactly where they left off!

### 6. Operational Control: Change Second-in-Command
Before Sebas dies, he can dynamically change who becomes the next leader. Let's make Jhonny the most important node:
```bash
curl -X POST http://localhost:8001/api/v1/leader/control/set_priority \
     -H "Content-Type: application/json" \
     -d '{"node_id": "node_jhonny", "priority": 999}'
```
Now, if Sebas dies, **Jhonny** will take over instead of Juanjo.
