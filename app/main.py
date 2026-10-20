
from fastapi import FastAPI
from app.api.ai10_review_api import router as ai10_review_router

app = FastAPI(
    title="RADAR 2.0 AI-10",
    description="조치 제안 문장 초안 생성 서비스",
    version="0.1.0",
)
app.include_router(ai10_review_router)


@app.get("/")
def root():
    return {
        "service": "RADAR AI-10",
        "status": "running",
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "module": "AI-10",
    }
