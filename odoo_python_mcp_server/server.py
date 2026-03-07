import os
from typing import Any, Dict, List, Optional

import httpx
from mcp.server.fastmcp import FastMCP


class OdooMCPClient:
    def __init__(
        self,
        base_url: str,
        db: Optional[str],
        token: Optional[str],
        login: Optional[str],
        api_key: Optional[str],
    ):
        self.base_url = base_url.rstrip("/")
        self.db = db
        self.token = token
        self.login = login
        self.api_key = api_key

    def _endpoint(self, path: str) -> str:
        url = f"{self.base_url}{path}"
        if self.db:
            sep = "&" if "?" in url else "?"
            url = f"{url}{sep}db={self.db}"
        return url

    @staticmethod
    def _unwrap(data: Any) -> Any:
        if isinstance(data, dict) and "error" in data:
            err = data.get("error") or {}
            message = (
                err.get("data", {}).get("message")
                or err.get("message")
                or str(err)
            )
            raise RuntimeError(message)
        if isinstance(data, dict) and "result" in data:
            return data["result"]
        return data

    async def _post(self, path: str, payload: Dict[str, Any]) -> Any:
        if self.token and "token" not in payload:
            payload["token"] = self.token
        if self.login and "login" not in payload:
            payload["login"] = self.login
        if self.api_key and "api_key" not in payload:
            payload["api_key"] = self.api_key
        if self.db and "db" not in payload:
            payload["db"] = self.db
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(self._endpoint(path), json=payload)
            response.raise_for_status()
            return self._unwrap(response.json())

    async def ping(self) -> Dict[str, Any]:
        return await self._post("/mcp/ping", {})

    async def models(self) -> List[Dict[str, Any]]:
        return await self._post("/mcp/models", {})

    async def fields(
        self, model: str, field_names: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"model": model}
        if field_names:
            payload["field_names"] = field_names
        return await self._post("/mcp/fields", payload)

    async def search_read(
        self,
        model: str,
        domain: Optional[List[Any]] = None,
        fields: Optional[List[str]] = None,
        limit: int = 100,
        offset: int = 0,
        order: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        payload: Dict[str, Any] = {
            "model": model,
            "domain": domain or [],
            "limit": limit,
            "offset": offset,
        }
        if fields:
            payload["fields"] = fields
        if order:
            payload["order"] = order
        return await self._post("/mcp/search_read", payload)

    async def read(self, model: str, ids: List[int], fields: Optional[List[str]] = None):
        payload: Dict[str, Any] = {"model": model, "ids": ids}
        if fields:
            payload["fields"] = fields
        return await self._post("/mcp/read", payload)

    async def create(
        self, model: str, values: Dict[str, Any], fields: Optional[List[str]] = None
    ) -> Any:
        payload: Dict[str, Any] = {"model": model, "values": values}
        if fields:
            payload["fields"] = fields
        return await self._post("/mcp/create", payload)

    async def write(self, model: str, ids: List[int], values: Dict[str, Any]) -> Any:
        payload: Dict[str, Any] = {"model": model, "ids": ids, "values": values}
        return await self._post("/mcp/write", payload)

    async def unlink(self, model: str, ids: List[int]) -> Any:
        payload: Dict[str, Any] = {"model": model, "ids": ids}
        return await self._post("/mcp/unlink", payload)


def _get_client() -> OdooMCPClient:
    base_url = os.getenv("ODOO_BASE_URL", "http://localhost:8069")
    db = os.getenv("ODOO_DB")
    token = os.getenv("ODOO_MCP_TOKEN")
    login = os.getenv("ODOO_LOGIN")
    api_key = os.getenv("ODOO_API_KEY")
    return OdooMCPClient(
        base_url=base_url, db=db, token=token, login=login, api_key=api_key
    )


mcp = FastMCP("Odoo MCP")
client = _get_client()


@mcp.tool()
async def ping() -> Dict[str, Any]:
    """Check connectivity to the Odoo MCP module."""
    return await client.ping()


@mcp.tool()
async def list_models() -> List[Dict[str, Any]]:
    """List all models available in Odoo."""
    return await client.models()


@mcp.tool()
async def list_fields(model: str, field_names: Optional[List[str]] = None) -> Dict[str, Any]:
    """Get field definitions for a model."""
    return await client.fields(model=model, field_names=field_names)


@mcp.tool()
async def search_read(
    model: str,
    domain: Optional[List[Any]] = None,
    fields: Optional[List[str]] = None,
    limit: int = 100,
    offset: int = 0,
    order: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Search and read records from a model."""
    return await client.search_read(
        model=model,
        domain=domain,
        fields=fields,
        limit=limit,
        offset=offset,
        order=order,
    )


@mcp.tool()
async def read_by_ids(
    model: str,
    ids: List[int],
    fields: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Read records by ID list."""
    return await client.read(model=model, ids=ids, fields=fields)


@mcp.tool()
async def create_record(
    model: str, values: Dict[str, Any], fields: Optional[List[str]] = None
) -> Any:
    """Create a record in a model."""
    return await client.create(model=model, values=values, fields=fields)


@mcp.tool()
async def update_records(model: str, ids: List[int], values: Dict[str, Any]) -> Any:
    """Update records by ID list."""
    return await client.write(model=model, ids=ids, values=values)


@mcp.tool()
async def delete_records(model: str, ids: List[int]) -> Any:
    """Delete records by ID list."""
    return await client.unlink(model=model, ids=ids)


if __name__ == "__main__":
    mcp.run()
