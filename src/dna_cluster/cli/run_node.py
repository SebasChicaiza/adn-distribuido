import uvicorn
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from dna_cluster.api.node_agent import router as node_router
from dna_cluster.config import settings
from dna_cluster.logging_setup import setup_logging
from dna_cluster.services.node_runtime import NodeRuntime

def main():
    setup_logging()
    
    # Initialize runtime
    runtime = NodeRuntime()
    runtime.start()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        task = asyncio.create_task(runtime.run_loop())
        yield
        task.cancel()

    app = FastAPI(title=f"DNA Node Agent ({settings.node_id})", lifespan=lifespan)
    app.state.runtime = runtime
    app.include_router(node_router, prefix="/api/v1")
    
    uvicorn.run(app, host=settings.api_host, port=settings.api_port)

if __name__ == "__main__":
    main()
