# 🧬 DNA Cluster: Team Demo Guide

This guide contains the exact steps for the team (Sebas, Juanjo, Nico, Jhonny, David) to run a successful, fault-tolerant DNA comparison across all laptops using the University Internal Network + Ngrok for remote access.

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

Edit your `.env` file based on your role:

```env
NODE_ID=node_yourname      # node_sebas, node_juanjo, etc.
ROLE_MODE=worker_standby

# PUBLIC_URL: Use your specific IP if in Uni, or ngrok if remote (David)
# Sebas:  http://192.168.208.96:8001
# Juanjo: http://192.168.208.92:8001
# Nico:   http://192.168.210.44:8001
# Jhonny: http://192.168.210.40:8001
# David:  https://magnesium-slicer-exhume.ngrok-free.dev
PUBLIC_URL=http://YOUR_ASSIGNED_IP_OR_NGROK:8001

# EVERYONE MUST USE THIS IDENTICAL LINE
CLUSTER_NODES=node_sebas,http://192.168.208.96:8001,100;node_juanjo,http://192.168.208.92:8001,90;node_nico,http://192.168.210.44:8001,80;node_jhonny,http://192.168.210.40:8001,70;node_david,https://magnesium-slicer-exhume.ngrok-free.dev,60

DATA_DIR=./data
INPUT_A_PATH=./data/input/a.fna
INPUT_B_PATH=./data/input/b.fna
LOG_LEVEL=INFO
```

---

## 🌐 Step 3: Connectivity

1. **Internal Uni Network (Sebas, Juanjo, Nico, Jhonny)**:
   Ensure your firewall allows incoming connections on port **8001**.
2. **Remote (David)**:
   Start Ngrok using the reserved domain:
   ```bash
   ngrok http 8001 --domain=magnesium-slicer-exhume.ngrok-free.dev
   ```
3. **Start the System (Everyone)**:
   ```bash
   python -m dna_cluster.cli.run_manager
   ```

---

## 🚀 Step 4: The Demo Sequence

### 1. Wait for Stability (60 Seconds)
The system has a **15-second startup grace period**. Wait one minute until everyone’s terminal shows `Registered node ...`.

### 2. Verify Cluster Status (Leader only)
The current leader (Sebas) checks the health:
```bash
curl http://localhost:8001/api/v1/leader/control/status
```

### 3. Trigger the Job (Leader only)
```bash
curl -X POST http://localhost:8001/api/v1/leader/job/create \
     -H "Content-Type: application/json" \
     -d '{"job_id": "massive_demo_job"}'
```

---

## 💥 Step 5: Chaos Testing (Failover)

1. **The "Assassination"**: Sebas hits `CTRL+C`.
2. **The Wait**: For 45 seconds, the cluster observes silence.
3. **The Promotion**: Juanjo (Priority 90) will log:
   `Promoted to LEADER! New term: 2`.
4. **The Reconnection**: Nico, Jhonny, and David will automatically find the new leader at `http://192.168.208.92:8001` and resume work.
