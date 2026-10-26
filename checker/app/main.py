"""FastAPI app: GET /health, GET /lists, POST /check."""

import hmac
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Header, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .ja import Analyzer
from .lists import load_lists
from .models import CheckRequest, CheckResponse, ErrorResponse, ListInfo, ListsResponse

LISTS_DIR = Path(os.environ.get("VOCAB_GUARD_LISTS", Path(__file__).resolve().parents[2] / "lists"))
MAX_TEXT_CHARS = int(os.environ.get("MAX_TEXT_CHARS", "20000"))
MAX_BODY_BYTES = 1_000_000
SUPPORTED_LANGS = {"ja"}
# When set, POST /check requires a matching X-API-Key header.
CHECKER_API_KEY = os.environ.get("CHECKER_API_KEY", "")


class APIError(Exception):
    def __init__(self, status: int, error: str, message: str) -> None:
        self.status, self.error, self.message = status, error, message


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.lists = load_lists(LISTS_DIR)
    app.state.analyzer = Analyzer()
    yield


app = FastAPI(
    title="vocab-guard checker",
    version="0.1.0",
    lifespan=lifespan,
    responses={400: {"model": ErrorResponse}, 413: {"model": ErrorResponse}},
)


@app.exception_handler(APIError)
async def api_error(_: Request, exc: APIError) -> JSONResponse:
    return JSONResponse({"error": exc.error, "message": exc.message}, status_code=exc.status)


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    message = "; ".join(
        f"{'.'.join(str(p) for p in e['loc'] if p != 'body') or 'body'}: {e['msg']}"
        for e in exc.errors()
    )
    return JSONResponse({"error": "invalid_request", "message": message}, status_code=422)


@app.middleware("http")
async def limit_body_size(request: Request, call_next):
    length = request.headers.get("content-length", "")
    if length.isdigit() and int(length) > MAX_BODY_BYTES:
        return JSONResponse(
            {"error": "request_too_large", "message": f"body is over {MAX_BODY_BYTES} bytes"},
            status_code=413,
        )
    return await call_next(request)


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    if CHECKER_API_KEY and not hmac.compare_digest(
        (x_api_key or "").encode(), CHECKER_API_KEY.encode()
    ):
        raise APIError(401, "unauthorized", "missing or wrong X-API-Key header")


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.get("/lists")
def lists(request: Request) -> ListsResponse:
    return ListsResponse(
        lists=[
            ListInfo(
                name=lst.name,
                lang=lst.lang,
                level=lst.level,
                levels=list(lst.levels),
                words=len(lst.words),
                kanji=None if lst.kanji is None else len(lst.kanji),
            )
            for lst in request.app.state.lists.values()
        ]
    )


@app.post(
    "/check",
    response_model=CheckResponse,
    response_model_exclude_none=True,
    dependencies=[Depends(require_api_key)],
)
def check(req: CheckRequest, request: Request) -> CheckResponse:
    if not req.text.strip():
        raise APIError(422, "empty_text", "text is empty")
    if len(req.text) > MAX_TEXT_CHARS:
        raise APIError(
            413,
            "text_too_long",
            f"text has {len(req.text)} characters; the limit is {MAX_TEXT_CHARS}",
        )
    if req.lang not in SUPPORTED_LANGS:
        raise APIError(
            400, "unsupported_lang", f"lang {req.lang!r} is not supported; supported: ja"
        )
    available = request.app.state.lists
    lst = available.get(req.list_name)
    if lst is None:
        raise APIError(
            400,
            "unknown_list",
            f"unknown list {req.list_name!r}; available: {', '.join(sorted(available))}",
        )
    if lst.lang != req.lang:
        raise APIError(
            400, "lang_mismatch", f"list {lst.name!r} is for lang {lst.lang!r}, not {req.lang!r}"
        )

    result = request.app.state.analyzer.check(req.text, lst, req.allow, req.options)
    content = result.content_tokens
    return CheckResponse(
        passed=all(s.ok for s in result.sentences),
        pass_rate=round(result.matched_tokens / content, 4) if content else 1.0,
        content_tokens=content,
        sentences=result.sentences,
    )
