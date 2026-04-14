# 🧬 DNA Cluster

A distributed hybrid CPU+GPU DNA comparison cluster built in Python.

## Features

- **Distributed Execution**: Compare massive 3GB `.fna` files across multiple laptops.
- **Priority-Based Failover**: Automatic leader election based on static priorities.
- **Dynamic Scheduling**: Load balancing with stuck chunk detection and requeueing.
- **Telemetry Aware**: Scheduler monitors CPU/RAM to optimize chunk distribution.
- **Native Python**: No Docker or Kubernetes required. Runs on Windows, macOS, and Linux.

## Quick Start (Local Demo)

You can run a full 3-node cluster simulation on your own machine using the provided smoke test script.

```bash
# Ensure you have Python 3.12+ and dependencies installed
pip install -r requirements.txt
pip install -e .

# Run the automated smoke test
./scripts/smoke_test_local.sh
```

The script will start a Leader, a Standby, and a Worker on different ports, run a job, and perform a failover test.

## Manual Cluster Setup

1. **Configure Environment**:
   Copy `.env.example` to `.env` and set your `NODE_ID` and `PUBLIC_URL`.
   ```env
   NODE_ID=node_sebas
   PUBLIC_URL=https://your-ngrok-url.ngrok-free.dev
   ```

2. **Expose Ports**:
   If using ngrok, expose port **8001**:
   ```bash
   ngrok http 8001
   ```

3. **Start the Cluster**:
   ```bash
   python -m dna_cluster.cli.run_manager
   ```

4. **Trigger a Job**:
   ```bash
   curl -X POST http://localhost:8001/api/v1/leader/job/create \
        -H "Content-Type: application/json" \
        -d '{"job_id": "my_first_job"}'
```

## Documentation

- [Team Execution Guide](TEAM_INSTRUCTIONS.md): Comprehensive guide for team-wide setup and chaos testing.
- [API Reference](docs/API.md): Details on control and status endpoints.

## Testing

```bash
pytest tests/
```
