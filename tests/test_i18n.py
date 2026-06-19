import asyncio

from fastapi import HTTPException, Request, Response

from app.api.routes import tr_complete
from app.core.i18n import get_language, normalize_language, reset_language, set_language, tr
from app.main import request_language


def test_normalize_language_supports_only_german_and_english():
    assert normalize_language("en-US,en;q=0.9") == "en"
    assert normalize_language("de-DE,de;q=0.9") == "de"
    assert normalize_language("fr-FR,fr;q=0.9") == "de"


def test_translation_context_can_switch_language():
    token = set_language("en")
    try:
        assert tr("api.code_required").startswith("The request body")
    finally:
        reset_language(token)


def test_api_error_uses_requested_language():
    token = set_language("en-US")
    try:
        try:
            asyncio.run(tr_complete({"session_id": "dummy"}))
        except HTTPException as error:
            assert error.status_code == 400
            assert error.detail.startswith("The request body")
        else:
            raise AssertionError("Expected a missing-code error")
    finally:
        reset_language(token)


def test_api_falls_back_to_german_for_french():
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/health",
            "headers": [(b"accept-language", b"fr-FR")],
        }
    )

    async def call_next(_request):
        assert get_language() == "de"
        return Response()

    response = asyncio.run(request_language(request, call_next))

    assert response.headers["Content-Language"] == "de"
