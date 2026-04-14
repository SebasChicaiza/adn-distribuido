import uuid

def generate_job_id() -> str:
    return f"job_{uuid.uuid4().hex[:8]}"

def generate_node_id() -> str:
    return f"node_{uuid.uuid4().hex[:8]}"
