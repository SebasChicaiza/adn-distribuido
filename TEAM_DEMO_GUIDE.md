# 🧬 DNA Cluster: Team Demo Guide

This guide contains the exact steps for the team (Sebas, Juanjo, Nico, Jhonny, David) to run a successful, fault-tolerant DNA comparison across all laptops.

---

## 🛠️ Step 1: Environment Preparation (Everyone)

1. **Update your repository**:
   ```bash
   git pull origin main
   ```
2. **Clean old data**:
   To avoid state conflicts, delete old logs and state files:
   ```bash
   # Linux/macOS
   rm -rf data/state/* data/work/* data/output/* data/normalized/* *.log
   # Windows (PowerShell)
   Remove-Item -Recurse -Force data\state\*, data\work\*, data\output\*, data\normalized\*
   ```
3. **Ensure DNA files are present**:
   Place `a.fna` and `b.fna` in `data/input/`.

---

## ⚙️ Step 2: Configuration (Everyone)

Edit your `.env` file. **Do not skip this.**

```env
NODE_ID=node_yourname      # node_sebas, node_juanjo, etc.
ROLE_MODE=worker_standby
PUBLIC_URL=https://your-ngrok-url.ngrok-free.dev

# EVERYONE MUST USE THIS IDENTICAL LINE
CLUSTER_NODES=node_sebas,https://kristy-vertebral-toilfully.ngrok-free.dev,100;node_juanjo,https://ducking-photo-tiny.ngrok-free.dev,90;node_nico,https://graves-angelfish-disclose.ngrok-free.dev,80;node_jhonny,https://item-overrun-glorified.ngrok-free.dev,70;node_david,https://magnesium-slicer-exhume.ngrok-free.dev,60

DATA_DIR=./data
INPUT_A_PATH=./data/input/a.fna
INPUT_B_PATH=./data/input/b.fna
LOG_LEVEL=INFO
```

---

## 🌐 Step 3: Connectivity (Everyone)

1. **Start Ngrok** (Use Port 8001):
   ```bash
   # Use your specific reserved domain if you have one
   ngrok http 8001
   ```
2. **Start the System**:
   ```bash
   python -m dna_cluster.cli.run_manager
   ```

---

## 🚀 Step 4: The Demo Sequence

### 1. Wait for Stability (60 Seconds)
The system has a **15-second startup grace period**. Wait one minute until everyone’s terminal shows `Registered node ...`.

### 2. Verify Cluster Status (Leader only)
The current leader (highest priority node online) checks the health:
```bash
curl http://localhost:8001/api/v1/leader/control/status
```

### 3. Trigger the Job (Leader only)
```bash
curl -X POST http://localhost:8001/api/v1/leader/job/create \
     -H "Content-Type: application/json" \
     -d '{"job_id": "team_demo_job"}'
```

### 4. Observe the Swarm
- **Workers**: Will log `Assigned chunk ...` and `Finished processing ...`.
- **Leader**: Will log `Committed chunk ...`.

---

## 💥 Step 5: Chaos Testing (Failover)

1. **The "Assassination"**: The current Leader (e.g., Sebas) hits `CTRL+C`.
2. **The Wait**: For 45 seconds, nothing seems to happen (this is the lease timeout).
3. **The Promotion**: The next person in the priority list (e.g., Juanjo) will log:
   `Promoted to LEADER! New term: 2`.
4. **The Reconnection**: All other nodes will log `Found new active leader...` and resume work automatically.

---

## 🔍 Troubleshooting

- **"Ignoring state sync with older term"**: This is normal during the first 15 seconds of startup while the cluster stabilizes. If it persists after 1 minute, check if two people have the same `NODE_ID`.
- **Worker not finding leader**: Ensure the `PUBLIC_URL` in your `.env` exactly matches your current ngrok URL.
- **Port 8001 busy**: Kill any hanging python processes: `pkill -9 python`.
