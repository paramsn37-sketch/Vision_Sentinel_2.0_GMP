"""FastAPI entry point. Routers are mounted in `app.api`; this module only builds the app."""

from fastapi import FastAPI

app = FastAPI(title="Vision Sentinel", version="2.0.0.dev0")


@app.get("/api/v1/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
