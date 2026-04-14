# DNA Cluster

A distributed hybrid CPU+GPU DNA comparison cluster built in Python.

## Current Milestone: Single Leader + Distributed Execution

This phase introduces a fully functional distributed execution loop over HTTP. Workers register to the leader, heartbeat to stay active, poll for chunks, execute work locally, and upload results to a durable parts directory where the final output is assembled.

### Features Working:

- Worker -> Leader HTTP Registration
- Background Heartbeat mechanism
- REST API for triggering a comparison job `POST /job/create`
- Distributed Job chunking and assignment via HTTP polling (`POST /chunk/request_work`)
- Local chunk comparison and result upload (`POST /chunk/result`)
- Durable commit state and cluster state tracking on the Leader
- Final `.fna` reconstruction upon job completion

## Setup

1. Create a virtual environment and install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

2. Configure environment:

```bash
cp .env.example .env
# Ensure LEADER_URL matches where your leader runs. By default: http://localhost:8001
```

## Running the Cluster Demo (2 Processes)

You can run the full distributed compare process locally using two terminals.

1. Create dummy input data (Make sure to run this from the project root):

```bash
mkdir -p data/input
echo -e ">seq1\nATCGATCG\n>seq2\nNNAA" > data/input/a.fna
echo -e ">seq1\nATTGATCG\n>seq2\nCCAA" > data/input/b.fna
```

# Fix errors

pip install -e .

2. Start the Leader Agent (Terminal 1):

```bash
source .venv/bin/activate
python -m dna_cluster.cli.run_manager
```

3. Start the Node Agent (Terminal 2):

```bash
source .venv/bin/activate
python -m dna_cluster.cli.run_node
```

4. Trigger a Distributed Job (Terminal 3):

```bash
curl -X POST http://localhost:8001/api/v1/leader/job/create \
     -H "Content-Type: application/json" \
     -d '{"job_id": "test_distributed_job_1"}'
```

Watch the logs on both Terminal 1 and 2. The leader will chunk the data, the worker will pick it up via polling, execute it locally, upload the `.res` file, and the leader will assemble `data/output/result_test_distributed_job_1.fna`.

## Real-World Setup (Ngrok & Teammates)

To connect laptops across different networks, you only need to expose the **Leader Agent** to the public internet using `ngrok`.

### Step 1: The Leader (You)
1. Ensure your `.env` has `LEADER_URL=http://localhost:8001`.
2. Start your Leader Agent: `python -m dna_cluster.cli.run_manager`.
3. In a new terminal, expose port 8001 via ngrok:
   ```bash
   ngrok http 8001
   ```
4. Copy the `https://<your-id>.ngrok.app` URL provided by ngrok. **Share this URL with your team.**

### Step 2: The Workers (Your Teammates)
1. They clone the repo and run `pip install -e .`
2. **CRITICAL:** They must place the exact same 3GB `.fna` files in their `data/input/` folders so their local hashes match yours.
3. They configure their `.env` files:
   ```env
   NODE_ID=node_juanjo  # (or node_nico, node_jhonny)
   ROLE_MODE=worker
   LEADER_URL=https://<your-id>.ngrok.app  # Paste the URL you shared!
   ```
4. They start their Node Agent:
   ```bash
   python -m dna_cluster.cli.run_node
   ```

### Step 3: Verifying the Connection
As soon as your teammates start their nodes, look at your **Leader Agent terminal logs**. You should immediately see:
- `[INFO] Node registered: node_juanjo`
- `[INFO] "POST /api/v1/leader/register HTTP/1.1" 200 OK`
- Continuous `heartbeat` and `request_work` POSTs from their machines.

Once everyone is connected, trigger the job exactly like the local demo!

## Testing

Run unit tests with pytest:

```bash
pytest tests/
```

## Remaining Gaps / Next Phase

- **Leader Failover:** The state store now accurately models known nodes and jobs, but the logic to promote a Standby Node to Leader via priority election is not yet active.
- **Worker Rejoin / Retry:** Reassigning chunks from offline/failed workers is stubbed but needs robust timeout enforcement via heartbeat drops.
- **Pluggable GPU Backend:** Currently entirely CPU-bound. Needs a CuPy/Numba or OpenCL interface to selectively execute chunks on GPUs when `gpu_available` is True.
