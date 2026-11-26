from fastapi import Depends, FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.routes import appointments, assistant, auth, dashboard, doctors, guides, insights, retention, patient_documents


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Terra Family Clinic API")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={"detail": {"code": "validation_error", "message": "The request is invalid."}},
        )

    for module in (auth, doctors, appointments, dashboard, guides, insights, assistant, retention, patient_documents):
        app.include_router(module.router, prefix="/api")

    @app.get("/health")
    def health(db: Session = Depends(get_db)):
        try:
            db.execute(text("SELECT 1"))
        except SQLAlchemyError:
            return JSONResponse(status_code=503, content={"status": "error", "db": "error"})
        return {"status": "ok", "db": "ok"}

    return app


app = create_app()
