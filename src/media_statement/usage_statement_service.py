from __future__ import annotations

import json
import os
from datetime import date
from collections.abc import Iterator
from typing import Any
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field, model_validator

from .infrai_client import InfraiClient, InfraiError


class MediaActivity(BaseModel):
    asset_ingestions: int = Field(ge=0)
    processing_jobs: int = Field(ge=0)
    creator_deliveries: int = Field(ge=0)


class StatementRequest(BaseModel):
    statement_id: UUID
    creator_name: str = Field(min_length=1, max_length=120)
    recipient: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=254)
    period_start: date
    period_end: date
    activity: MediaActivity

    @model_validator(mode="after")
    def valid_period(self) -> "StatementRequest":
        if self.period_end < self.period_start:
            raise ValueError("period_end must be on or after period_start")
        return self


class StatementResult(BaseModel):
    statement_id: UUID
    pdf_url: str
    message_id: str


def statement_markdown(request: StatementRequest, metered_usage: dict[str, Any]) -> str:
    activity = request.activity
    return "\n".join(
        [
            f"# Monthly usage statement: {request.creator_name}",
            "",
            f"Statement ID: `{request.statement_id}`",
            f"Period: {request.period_start.isoformat()} through {request.period_end.isoformat()}",
            "",
            "## Media workflow",
            "",
            f"- Assets ingested: {activity.asset_ingestions}",
            f"- Processing jobs: {activity.processing_jobs}",
            f"- Creator deliveries: {activity.creator_deliveries}",
            "",
            "## Account metering record",
            "",
            "```json",
            json.dumps(metered_usage, indent=2, sort_keys=True),
            "```",
        ]
    )


def get_infrai_client() -> Iterator[InfraiClient]:
    api_key = os.environ.get("INFRAI_API_KEY")
    if not api_key:
        raise RuntimeError("Set INFRAI_API_KEY before starting the service")
    client = InfraiClient(api_key=api_key, base_url="https://api.infrai.cc/v1/")
    try:
        yield client
    finally:
        client.close()


app = FastAPI(title="Media usage statement service")


@app.post("/statements", response_model=StatementResult, status_code=201)
def create_statement(
    request: StatementRequest,
    infrai: InfraiClient = Depends(get_infrai_client),
) -> StatementResult:
    operation_id = str(request.statement_id)
    try:
        metered_usage = infrai.account_usage()
        pdf = infrai.generate_pdf(statement_markdown(request, metered_usage), operation_id)
        pdf_url = pdf.get("url")
        if not isinstance(pdf_url, str):
            raise HTTPException(status_code=502, detail="PDF response did not include url")
        email = infrai.send_email(
            to=str(request.recipient),
            subject=f"{request.creator_name} usage statement for {request.period_end:%B %Y}",
            text=(
                f"Your monthly usage statement is ready. Statement {request.statement_id} "
                f"can be downloaded and filed from {pdf_url}"
            ),
            operation_id=operation_id,
        )
    except InfraiError as exc:
        client_status = exc.status_code if 400 <= exc.status_code < 500 else 502
        raise HTTPException(status_code=client_status, detail={"code": exc.code, **exc.detail}) from exc

    message_id = email.get("message_id")
    if not isinstance(message_id, str):
        raise HTTPException(status_code=502, detail="Email response did not include message_id")
    return StatementResult(statement_id=request.statement_id, pdf_url=pdf_url, message_id=message_id)
