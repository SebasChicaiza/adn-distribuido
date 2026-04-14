import uvicorn
from fastapi import FastAPI
from dna_cluster.api.leader_api import router as leader_router
from dna_cluster.config import settings
from dna_cluster.logging_setup import setup_logging
from dna_cluster.services.leader_runtime import LeaderRuntime

def main():
    setup_logging()
    
    runtime = LeaderRuntime()
    runtime.start()

    app = FastAPI(title=f"DNA Leader Agent ({settings.node_id})")
    app.state.runtime = runtime
    app.include_router(leader_router, prefix="/api/v1/leader")
    
    # Note: A node can be both worker and leader, so it might include both routers.
    # For simplicity, we separate them as entry points here.
    
    uvicorn.run(app, host=settings.api_host, port=settings.api_port + 1) # run manager on different port for local testing

if __name__ == "__main__":
    main()
