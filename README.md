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

### Step 1: The Leader (Sebas)
1. Ensure your `.env` specifies all cluster nodes mapping to their public URLs and priorities. For example:
   ```env
   NODE_ID=node_sebas
   ROLE_MODE=worker_standby
   CLUSTER_NODES=node_sebas,https://sebas.ngrok.app,100;node_juanjo,https://juanjo.ngrok.app,90;node_nico,https://nico.ngrok.app,10
   ```
2. Expose your port 8001 via ngrok:
   ```bash
   ngrok http 8001 --domain=sebas.ngrok.app
   ```
3. Start your Manager (runs both Node + Leader routers):
   ```bash
   python -m dna_cluster.cli.run_manager
   ```

### Step 2: The Workers & Standbys (Juanjo, Nico, Jhonny, David)
Tell your friends to run exactly these commands in their terminals:

1. **Clone the repository and enter the directory:**
   ```bash
   git clone git@github.com:SebasChicaiza/adn-distribuido.git
   cd adn-distribuido
   ```

2. **Create a virtual environment and install the package:**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # (On Windows, they might need: .venv\Scripts\activate)
   pip install -r requirements.txt
   pip install -e .
   ```

3. **CRITICAL STEP - Download the 3GB DNA Files:**
   They **MUST** place the exact same 3GB `a.fna` and `b.fna` files into their `data/input/` folders so their local file hashes match yours.

4. **Configure their `.env` file:**
   They need to create a `.env` file in the root of the project with these exact contents. **IMPORTANT**: Every node needs its own ngrok URL to be a standby!
   ```env
   NODE_ID=node_juanjo  # Tell Nico to use node_nico, Jhonny to use node_jhonny, etc.
   ROLE_MODE=worker_standby
   PUBLIC_URL=https://juanjo.ngrok.app # Their own personal ngrok URL!
   CLUSTER_NODES=node_sebas,https://sebas.ngrok.app,100;node_juanjo,https://juanjo.ngrok.app,90;node_nico,https://nico.ngrok.app,10
   ```

5. **Start their nodes:**
   If they are a standby, they should expose their port 8001 and run the manager:
   ```bash
   ngrok http 8001 --domain=juanjo.ngrok.app
   python -m dna_cluster.cli.run_manager
   ```

### Step 3: Verifying the Connection & Failover
- The node with the highest priority will automatically become the Leader (`node_sebas`).
- Workers will poll the nodes in `CLUSTER_NODES` until they find the active Leader.
- The active Leader continuously pushes a state snapshot to all standbys.
- If you (Sebas) shut down your laptop, `node_juanjo` (priority 90) will detect the missing heartbeats after 15 seconds, increment the term, and promote itself to Leader. The other workers will seamlessly reconnect and resume executing uncommitted chunks!

### Step 4: Run the 3GB Comparison Job!
Once you see logs confirming that Juanjo, Nico, Jhonny, and David have all registered with your Leader Agent, you trigger the distributed job from your laptop!

Run this in a third terminal on your laptop:
```bash
curl -X POST http://localhost:8001/api/v1/leader/job/create \
     -H "Content-Type: application/json" \
     -d '{"job_id": "massive_3gb_job"}'
```

Your leader node will generate hundreds of chunks. The next time your friends' nodes poll you via ngrok, they will automatically be handed a piece of the work. You'll see the `.res` chunks being uploaded back to your machine until the job completes and auto-assembles the final file!

## Testing

Run unit tests with pytest:

```bash
pytest tests/
```

## Remaining Gaps / Next Phase

- **Leader Failover:** The state store now accurately models known nodes and jobs, but the logic to promote a Standby Node to Leader via priority election is not yet active.
- **Worker Rejoin / Retry:** Reassigning chunks from offline/failed workers is stubbed but needs robust timeout enforcement via heartbeat drops.
- **Pluggable GPU Backend:** Currently entirely CPU-bound. Needs a CuPy/Numba or OpenCL interface to selectively execute chunks on GPUs when `gpu_available` is True.
