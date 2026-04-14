import uvicorn
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from dna_cluster.api.leader_api import router as leader_router
from dna_cluster.api.node_agent import router as node_router
from dna_cluster.config import settings
from dna_cluster.logging_setup import setup_logging
from dna_cluster.services.leader_runtime import LeaderRuntime

def main():
    setup_logging()
    
    runtime = LeaderRuntime()
    runtime.start()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        task = asyncio.create_task(runtime.run_loop())
        yield
        task.cancel()

    app = FastAPI(title=f"DNA Leader Agent ({settings.node_id})", lifespan=lifespan)
    app.state.runtime = runtime
    app.include_router(node_router, prefix="/api/v1")
    app.include_router(leader_router, prefix="/api/v1/leader")
    
    uvicorn.run(app, host=settings.api_host, port=settings.api_port)

if __name__ == "__main__":
    main()
