import pytest
import time
from dna_cluster.models.node import NodeInfo
from dna_cluster.models.chunk import ChunkInfo, ChunkState
from dna_cluster.models.cluster import ClusterState
from dna_cluster.models.job import JobInfo
from dna_cluster.services.leader_runtime import LeaderRuntime

@pytest.fixture
def leader():
    lr = LeaderRuntime()
    lr.state = ClusterState(term=1, leader_id="leader")
    lr.is_leader = True
    return lr

def test_telemetry_persistence(leader):
    node = NodeInfo(node_id="worker1", role_mode="worker", leader_priority=10, public_url="", available_ram_bytes=1000)
    leader.register_node(node)
    
    assert "worker1" in leader.state.nodes
    assert leader.state.nodes["worker1"].available_ram_bytes == 1000
    
    node.available_ram_bytes = 2000
    leader.update_node_heartbeat(node)
    assert leader.state.nodes["worker1"].available_ram_bytes == 2000

def test_pinned_node_mode(leader):
    n1 = NodeInfo(node_id="n1", role_mode="worker", leader_priority=10, public_url="")
    n2 = NodeInfo(node_id="n2", role_mode="worker", leader_priority=10, public_url="")
    leader.register_node(n1)
    leader.register_node(n2)
    
    leader.state.scheduler_mode = "pin_single_node"
    leader.state.pinned_node_id = "n1"
    
    job = JobInfo(job_id="job1", input_a_hash="", input_b_hash="", state="running")
    chunk = ChunkInfo(chunk_id="c1", job_id="job1", start_offset=0, length=10)
    job.chunks["c1"] = chunk
    leader.state.active_jobs["job1"] = job
    
    # n2 requests work, should get None
    res = leader.request_work("n2")
    assert res is None
    
    # n1 requests work, should get the chunk
    res = leader.request_work("n1")
    assert res is not None
    assert res[1].chunk_id == "c1"
    assert res[1].assigned_node == "n1"

def test_weighted_scheduling_prefers_strong_node(leader):
    n_weak = NodeInfo(node_id="weak", role_mode="worker", leader_priority=10, public_url="", available_ram_bytes=1024, cpu_count=1)
    n_strong = NodeInfo(node_id="strong", role_mode="worker", leader_priority=10, public_url="", available_ram_bytes=16*1024**3, cpu_count=8)
    
    leader.register_node(n_weak)
    leader.register_node(n_strong)
    
    leader.state.scheduler_mode = "weighted"
    
    job = JobInfo(job_id="job2", input_a_hash="", input_b_hash="", state="running")
    chunk = ChunkInfo(chunk_id="c2", job_id="job2", start_offset=0, length=10)
    job.chunks["c2"] = chunk
    leader.state.active_jobs["job2"] = job
    
    # Weak node requests work, should be rejected because strong node is much better
    res = leader.request_work("weak")
    assert res is None
    
    # Strong node requests work, should get it
    res = leader.request_work("strong")
    assert res is not None
    assert res[1].assigned_node == "strong"

def test_stuck_chunk_requeue(leader):
    n1 = NodeInfo(node_id="n1", role_mode="worker", leader_priority=10, public_url="", last_seen_at=time.time() - 40.0) # Dead node
    leader.register_node(n1)
    
    job = JobInfo(job_id="job3", input_a_hash="", input_b_hash="", state="running")
    chunk = ChunkInfo(chunk_id="c3", job_id="job3", start_offset=0, length=10, state=ChunkState.ASSIGNED, assigned_node="n1", assigned_at=time.time() - 70.0)
    job.chunks["c3"] = chunk
    leader.state.active_jobs["job3"] = job
    
    # Run stuck check
    leader._check_stuck_chunks()
    
    # Chunk should be requeued
    assert leader.state.active_jobs["job3"].chunks["c3"].state == ChunkState.RETRY
    assert leader.state.active_jobs["job3"].chunks["c3"].assigned_node is None
