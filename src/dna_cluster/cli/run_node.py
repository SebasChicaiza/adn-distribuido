import uvicorn
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

    app = FastAPI(title=f"DNA Node Agent ({settings.node_id})")
    app.state.runtime = runtime
    app.include_router(node_router, prefix="/api/v1")
    
    import asyncio
    @app.on_event("startup")
    async def startup_event():
        asyncio.create_task(runtime.run_loop())
    
    uvicorn.run(app, host=settings.api_host, port=settings.api_port)

if __name__ == "__main__":
    main()
