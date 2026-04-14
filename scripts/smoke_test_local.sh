#!/bin/bash
# Local Smoke Test for DNA Cluster
# Runs Leader, Standby, and Worker on localhost.

set -e

# Setup environment
export API_HOST=127.0.0.1
export DATA_DIR=$(pwd)/data_smoke
export LOG_LEVEL=INFO
export CLUSTER_NODES="node_leader,http://localhost:8001,100;node_standby,http://localhost:8002,90"
export INPUT_A_PATH=$DATA_DIR/input/a.fna
export INPUT_B_PATH=$DATA_DIR/input/b.fna

# Clean up
rm -rf $DATA_DIR
mkdir -p $DATA_DIR/input $DATA_DIR/state $DATA_DIR/work $DATA_DIR/output $DATA_DIR/normalized
if [ ! -f $DATA_DIR/input/a.fna ]; then
    echo -e ">seq1\nATCGATCG\n>seq2\nNNAA" > $DATA_DIR/input/a.fna
    echo -e ">seq1\nATTGATCG\n>seq2\nCCAA" > $DATA_DIR/input/b.fna
fi

# Start Leader
echo "Starting Leader (node_leader)..."
NODE_ID=node_leader API_PORT=8001 PUBLIC_URL=http://localhost:8001 ROLE_MODE=worker_standby python -m dna_cluster.cli.run_manager > leader.log 2>&1 &
LEADER_PID=$!

# Start Standby
echo "Starting Standby (node_standby)..."
NODE_ID=node_standby API_PORT=8002 PUBLIC_URL=http://localhost:8002 ROLE_MODE=worker_standby python -m dna_cluster.cli.run_manager > standby.log 2>&1 &
STANDBY_PID=$!

# Start Worker
echo "Starting Worker (node_worker)..."
NODE_ID=node_worker API_PORT=8003 PUBLIC_URL=http://localhost:8003 ROLE_MODE=worker python -m dna_cluster.cli.run_node > worker.log 2>&1 &
WORKER_PID=$!

# Helper to kill processes on exit
cleanup() {
    echo "Cleaning up..."
    kill $LEADER_PID $STANDBY_PID $WORKER_PID 2>/dev/null || true
}
trap cleanup EXIT

# Wait for startup
echo "Waiting for cluster to start..."
sleep 10

# Check status
echo "Checking cluster status..."
curl -s http://localhost:8001/api/v1/leader/control/status | grep -q "node_leader" && echo "Leader is up" || (echo "Leader failed"; exit 1)
# Wait a bit more for registration
for i in {1..10}; do
    if curl -s http://localhost:8001/api/v1/leader/control/status | grep -q "node_worker"; then
        echo "Worker registered!"
        break
    fi
    sleep 2
    if [ $i -eq 10 ]; then
        echo "Worker not found after timeout!"
        curl -s http://localhost:8001/api/v1/leader/control/status
        exit 1
    fi
done

# Trigger Job
echo "Triggering job..."
curl -X POST http://localhost:8001/api/v1/leader/job/create \
     -H "Content-Type: application/json" \
     -d '{"job_id": "smoke_job"}'

# Wait for job completion
echo "Waiting for job to complete..."
for i in {1..30}; do
    if [ -f $DATA_DIR/output/result_smoke_job.fna ]; then
        echo "Job completed successfully!"
        break
    fi
    sleep 2
    if [ $i -eq 30 ]; then
        echo "Job timed out!"
        exit 1
    fi
done

# Failover Test
echo "Killing leader for failover test..."
kill $LEADER_PID
echo "Waiting for standby promotion (timeout 60s)..."
# We need to wait more than 45s for the lease to expire
for i in {1..40}; do
    STATUS=$(curl -s http://localhost:8002/api/v1/status || echo "{}")
    if echo "$STATUS" | grep -q '"is_leader":true'; then
        echo "Standby successfully promoted to leader!"
        break
    fi
    sleep 2
    if [ $i -eq 40 ]; then
        echo "Failover timed out!"
        exit 1
    fi
done

echo "Smoke test PASSED!"
