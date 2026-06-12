from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from src.interfaces.api.routes import jobs, live, meta, research

app = FastAPI(title="GoldenHandQuant API", version="0.2.0")
app.include_router(research.router, prefix="/api/research", tags=["research"])
app.include_router(live.router, prefix="/api/live", tags=["live"])
app.include_router(jobs.router, prefix="/api/jobs", tags=["jobs"])
app.include_router(meta.router, prefix="/api/meta", tags=["meta"])

_STATIC_DIR = Path(__file__).parent / "static"
app.mount("/ui", StaticFiles(directory=str(_STATIC_DIR), html=True), name="ui")


@app.middleware("http")
async def _no_cache_static(request, call_next):
    """前端无构建链直接改盘上文件, 浏览器强缓存会让用户拿到旧 JS/CSS。

    no-cache = 每次协商再验证 (ETag/304), 本机访问代价为零, 改完即生效。
    """
    response = await call_next(request)
    if request.url.path.startswith("/ui"):
        response.headers["Cache-Control"] = "no-cache"
    return response


@app.get("/", include_in_schema=False)
async def index_redirect():
    return RedirectResponse(url="/ui/", status_code=302)


@app.get("/health")
async def health_check():
    return {"status": "ok", "version": "0.2.0"}
