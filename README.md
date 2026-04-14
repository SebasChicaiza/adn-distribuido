# 🧬 DNA Cluster

A distributed DNA comparison cluster built in Python, designed for classroom demos and large-scale genetic sequence analysis.

## Features

- **Distributed Execution**: Compare massive 3GB `.fna` files across multiple nodes (laptops) using HTTP polling.
- **Robust Priority-Based Failover**: Automatic leader election with term precedence and priority-based tie-breaking.
- **Startup Grace Period**: Prevents race conditions during cluster-wide startup.
- **Telemetry Aware**: Scheduler monitors CPU/RAM to optimize chunk distribution.
- **Automated Smoke Test**: Integrated script to verify the entire lifecycle (election, processing, failover) on localhost.

## Quick Start (Local Demo)

You can simulate a full 3-node cluster (1 Leader, 1 Standby, 1 Worker) on your machine.

```bash
# 1. Install dependencies
pip install -r requirements.txt
pip install -e .

# 2. Run the automated smoke test
./scripts/smoke_test_local.sh
```

The script performs the following:
1. Starts a Leader (`node_leader`, port 8001, Priority 100).
2. Starts a Standby (`node_standby`, port 8002, Priority 90).
3. Starts a Worker (`node_worker`, port 8003).
4. Registers the worker and triggers a job.
5. Verifies processing and final output assembly.
6. Kills the Leader and verifies that the Standby promotes successfully.

## Manual Cluster Setup (Team Mode)

1. **Configure Environment**:
   Copy `.env.example` to `.env`. Set your `NODE_ID` (e.g., `node_juanjo`) and your `PUBLIC_URL` (if using ngrok).
   Ensure `CLUSTER_NODES` contains the full list of team members and their priorities.

2. **Expose Ports**:
   If using ngrok, expose port **8001**:
   ```bash
   ngrok http 8001
   ```

3. **Start the Node**:
   Run the manager on your laptop:
   ```bash
   python -m dna_cluster.cli.run_manager
   ```
   *Note: If you are the highest priority node online, you will automatically become the Leader.*

4. **Trigger a Job** (Leader only):
   ```bash
   curl -X POST http://localhost:8001/api/v1/leader/job/create \
        -H "Content-Type: application/json" \
        -d '{"job_id": "my_first_job"}'
   ```

## Documentation

- [Team Execution Guide](TEAM_INSTRUCTIONS.md): Detailed guide for team-wide setup, ngrok configuration, and chaos testing.

## Testing

```bash
# Run unit tests
pytest

# Run local smoke test
./scripts/smoke_test_local.sh
```

## Current Status

The system is **stabilized** and **demo-ready**. 
- ✅ Syntax and import integrity verified.
- ✅ Leadership election is deterministic (Term > Priority > NodeID).
- ✅ Startup race conditions resolved with a 15s grace period.
- ✅ Failover verified in local multi-node simulation.
- ✅ Distributed assembly of output verified.
