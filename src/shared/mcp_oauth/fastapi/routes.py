"""FastAPI router for OAuth 2.1 + PKCE endpoints.

Endpoints follow MCP June 2025 spec mandate:
- RFC 9728 Protected Resource Metadata
- RFC 8414 Authorization Server Metadata
- RFC 7636 PKCE S256
- Refresh-token rotation (single-use refresh)
"""

from fastapi import APIRouter, Form, HTTPException, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse


def build_oauth_router() -> APIRouter:
    """Build the OAuth router. Reads `request.app.state.oauth_service`."""
    router = APIRouter(tags=["oauth"])

    @router.get("/.well-known/oauth-protected-resource")
    async def prm_metadata(request: Request):
        """RFC 9728 Protected Resource Metadata."""
        service = request.app.state.oauth_service
        public_url = _public_url(request)
        return service.generate_prm_document(public_url)

    @router.get("/.well-known/oauth-authorization-server")
    async def authz_server_metadata(request: Request):
        """RFC 8414 Authorization Server Metadata."""
        public_url = _public_url(request)
        return {
            "issuer": public_url,
            "authorization_endpoint": f"{public_url}/authorize",
            "token_endpoint": f"{public_url}/token",
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code", "refresh_token"],
            "code_challenge_methods_supported": ["S256"],
            "token_endpoint_auth_methods_supported": ["none"],
        }

    @router.get("/authorize")
    async def authorize(
        request: Request,
        client_id: str = Query(...),
        redirect_uri: str = Query(...),
        code_challenge: str = Query(...),
        code_challenge_method: str = Query("S256"),
        state: str | None = Query(None),
    ):
        """Authorization code grant entry — PKCE S256 mandatory."""
        if code_challenge_method != "S256":
            raise HTTPException(400, "Only S256 code_challenge_method supported")
        service = request.app.state.oauth_service
        code = await service.generate_authorization_code(
            client_id=client_id,
            redirect_uri=redirect_uri,
            code_challenge=code_challenge,
            user_data={"client_id": client_id},
        )
        sep = "&" if "?" in redirect_uri else "?"
        target = f"{redirect_uri}{sep}code={code}"
        if state:
            target += f"&state={state}"
        return RedirectResponse(target, status_code=302)

    @router.post("/token")
    async def token(
        request: Request,
        grant_type: str = Form(...),
        code: str | None = Form(None),
        redirect_uri: str | None = Form(None),
        code_verifier: str | None = Form(None),
        refresh_token: str | None = Form(None),
    ):
        """Token endpoint — authorization_code or refresh_token grant."""
        service = request.app.state.oauth_service

        if grant_type == "authorization_code":
            if not (code and redirect_uri and code_verifier):
                raise HTTPException(400, "Missing code / redirect_uri / code_verifier")
            result = await service.exchange_code_for_tokens(code, redirect_uri, code_verifier)
        elif grant_type == "refresh_token":
            if not refresh_token:
                raise HTTPException(400, "Missing refresh_token")
            result = await service.refresh_tokens(refresh_token)
        else:
            raise HTTPException(400, f"Unsupported grant_type: {grant_type}")

        if not result:
            return JSONResponse(
                {"error": "invalid_grant", "error_description": "Invalid or expired credentials"},
                status_code=400,
            )

        access, ttype, expires_in, refresh = result
        return {
            "access_token": access,
            "token_type": ttype,
            "expires_in": expires_in,
            "refresh_token": refresh,
        }

    return router


def _public_url(request: Request) -> str:
    """Derive public-facing URL from request, honoring proxy headers."""
    scheme = request.headers.get("x-forwarded-proto") or request.url.scheme
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or request.url.netloc
    return f"{scheme}://{host}".rstrip("/")
