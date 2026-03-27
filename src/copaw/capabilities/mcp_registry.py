# -*- coding: utf-8 -*-
"""Official MCP registry discovery, install materialization, and upgrade helpers."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Literal
from urllib.parse import quote
from urllib.request import Request, urlopen

from pydantic import BaseModel, Field

from ..config.config import MCPClientConfig, MCPRegistryProvenance

_REGISTRY_BASE_URL = "https://registry.modelcontextprotocol.io"
_LIST_LIMIT_CAP = 24
_LIST_FETCH_LIMIT = 60
_LIST_MAX_FETCH_ROUNDS = 6
_CACHE_TTL = timedelta(minutes=10)
_HTTP_TIMEOUT_SECONDS = 20.0

_CATEGORY_DEFINITIONS: list[tuple[str, str, tuple[str, ...]]] = [
    ("browser", "浏览器", ("browser", "web", "page", "playwright", "puppeteer")),
    ("filesystem", "文件", ("file", "filesystem", "directory", "folder", "storage")),
    ("database", "数据库", ("database", "postgres", "mysql", "mongodb", "sqlite", "sql")),
    ("data", "数据", ("data", "sheet", "excel", "csv", "analytics", "report")),
    ("developer", "开发", ("code", "github", "git", "developer", "devops", "debug")),
    ("automation", "自动化", ("workflow", "automation", "orchestr", "routine", "sop")),
    ("communication", "沟通", ("slack", "discord", "email", "notion", "calendar", "meeting")),
    ("finance", "金融", ("trading", "finance", "portfolio", "market", "invest", "crypto")),
    ("ai", "AI", ("llm", "agent", "model", "prompt", "embedding", "rag")),
    ("search", "搜索", ("search", "crawl", "scrape", "monitor", "research", "knowledge")),
]

_TRANSPORT_ALIAS_MAP = {
    "streamable-http": "streamable_http",
    "streamable_http": "streamable_http",
    "http": "streamable_http",
    "sse": "sse",
    "stdio": "stdio",
}

_CACHE: dict[str, tuple[datetime, Any]] = {}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_text(value: object | None) -> str:
    return " ".join(str(value or "").strip().split())


def _normalize_transport(value: object | None) -> Literal["stdio", "streamable_http", "sse"]:
    normalized = str(value or "").strip().lower().replace("-", "_")
    mapped = _TRANSPORT_ALIAS_MAP.get(normalized.replace("_", "-")) or _TRANSPORT_ALIAS_MAP.get(normalized)
    if mapped in {"stdio", "streamable_http", "sse"}:
        return mapped
    return "stdio"


def _normalize_category(value: object | None) -> str:
    normalized = str(value or "").strip().lower()
    if normalized == "all":
        return "all"
    known = {item[0] for item in _CATEGORY_DEFINITIONS}
    return normalized if normalized in known else "all"


def _registry_request(url: str) -> Any:
    cache_key = hashlib.sha1(url.encode("utf-8")).hexdigest()
    cached = _CACHE.get(cache_key)
    now = _utc_now()
    if cached is not None and cached[0] >= now:
        return cached[1]

    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "CoPaw-MCP-Market/1.0",
        },
    )
    with urlopen(request, timeout=_HTTP_TIMEOUT_SECONDS) as response:
        payload = json.load(response)
    _CACHE[cache_key] = (now + _CACHE_TTL, payload)
    return payload


def clear_mcp_registry_cache() -> None:
    _CACHE.clear()


class McpRegistryCategory(BaseModel):
    key: str
    label: str


class McpRegistryInputField(BaseModel):
    key: str
    label: str
    source: Literal[
        "environment",
        "header",
        "url-variable",
        "runtime-argument",
        "package-argument",
    ]
    required: bool = False
    secret: bool = False
    description: str = ""
    default_value: Any = None
    format: str = "string"
    choices: list[str] = Field(default_factory=list)
    argument_name: str = ""
    argument_mode: Literal["named", "positional", "flag"] = "positional"
    repeated: bool = False
    value_hint: str = ""


class McpRegistryInstallOption(BaseModel):
    key: str
    label: str
    summary: str = ""
    install_kind: Literal["package", "remote"]
    transport: Literal["stdio", "streamable_http", "sse"]
    supported: bool = True
    support_reason: str = ""
    registry_type: str = ""
    identifier: str = ""
    version: str = ""
    runtime_command: str = ""
    url_template: str = ""
    input_fields: list[McpRegistryInputField] = Field(default_factory=list)


class McpRegistryCatalogItem(BaseModel):
    server_name: str
    title: str
    description: str = ""
    version: str = ""
    source_label: str = "Official MCP Registry"
    source_url: str = ""
    repository_url: str = ""
    website_url: str = ""
    category_keys: list[str] = Field(default_factory=list)
    transport_types: list[str] = Field(default_factory=list)
    suggested_client_key: str
    option_count: int = 0
    supported_option_count: int = 0
    install_supported: bool = False
    installed_client_key: str | None = None
    installed_via_registry: bool = False
    installed_version: str = ""
    update_available: bool = False
    routes: dict[str, str] = Field(default_factory=dict)


class McpRegistryCatalogSearchResponse(BaseModel):
    items: list[McpRegistryCatalogItem] = Field(default_factory=list)
    categories: list[McpRegistryCategory] = Field(default_factory=list)
    cursor: str | None = None
    next_cursor: str | None = None
    has_more: bool = False
    page_size: int = 12
    source_label: str = "Official MCP Registry"
    warnings: list[str] = Field(default_factory=list)


class McpRegistryCatalogDetailResponse(BaseModel):
    item: McpRegistryCatalogItem
    install_options: list[McpRegistryInstallOption] = Field(default_factory=list)
    categories: list[McpRegistryCategory] = Field(default_factory=list)
    matched_registry_client_key: str | None = None
    matched_registry_input_values: dict[str, Any] = Field(default_factory=dict)


class MaterializedMcpRegistryInstallPlan(BaseModel):
    client_key: str
    client: MCPClientConfig
    registry: MCPRegistryProvenance
    summary: str = ""
    version_changed: bool = False
    previous_version: str = ""


def list_mcp_registry_categories() -> list[McpRegistryCategory]:
    return [McpRegistryCategory(key="all", label="全部")] + [
        McpRegistryCategory(key=key, label=label)
        for key, label, _keywords in _CATEGORY_DEFINITIONS
    ]


def _display_title(server: dict[str, Any]) -> str:
    title = _normalize_text(server.get("title"))
    if title:
        return title
    name = _normalize_text(server.get("name"))
    if not name:
        return "Unnamed MCP Server"
    return name.split("/")[-1].replace("-", " ")


def _repository_url(server: dict[str, Any]) -> str:
    repository = server.get("repository")
    if isinstance(repository, dict):
        return _normalize_text(repository.get("url"))
    return ""


def _website_url(server: dict[str, Any]) -> str:
    return _normalize_text(server.get("websiteUrl"))


def _source_url(server_name: str) -> str:
    return (
        f"{_REGISTRY_BASE_URL}/v0/servers/"
        f"{quote(server_name, safe='')}/versions/latest"
    )


def _suggested_client_key(server_name: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", server_name).strip("_").lower()
    return normalized or "mcp_registry_server"


def _search_blob(server: dict[str, Any]) -> str:
    packages = server.get("packages") or []
    remotes = server.get("remotes") or []
    parts = [
        _normalize_text(server.get("name")),
        _normalize_text(server.get("title")),
        _normalize_text(server.get("description")),
        _repository_url(server),
        _website_url(server),
    ]
    for package in packages:
        if not isinstance(package, dict):
            continue
        parts.extend(
            [
                _normalize_text(package.get("registryType")),
                _normalize_text(package.get("identifier")),
                _normalize_text(package.get("runtimeHint")),
            ]
        )
    for remote in remotes:
        if not isinstance(remote, dict):
            continue
        parts.extend(
            [
                _normalize_text(remote.get("type")),
                _normalize_text(remote.get("url")),
            ]
        )
    return " ".join(part for part in parts if part).lower()


def infer_mcp_registry_categories(server: dict[str, Any]) -> list[str]:
    blob = _search_blob(server)
    categories = [
        key
        for key, _label, keywords in _CATEGORY_DEFINITIONS
        if any(keyword in blob for keyword in keywords)
    ]
    return categories or ["general"]


def _normalize_choices(values: object | None) -> list[str]:
    if not isinstance(values, list):
        return []
    return [str(item).strip() for item in values if str(item).strip()]


def _normalize_argument_mode(raw: dict[str, Any]) -> Literal["named", "positional", "flag"]:
    kind = _normalize_text(raw.get("type")).lower()
    name = _normalize_text(raw.get("name"))
    fmt = _normalize_text(raw.get("format")).lower()
    if kind == "named" or name.startswith("-"):
        if fmt in {"boolean", "bool"}:
            return "flag"
        return "named"
    if kind == "positional":
        return "positional"
    if fmt in {"boolean", "bool"} and name.startswith("-"):
        return "flag"
    return "positional"


def _build_argument_field(
    source: Literal["runtime-argument", "package-argument"],
    index: int,
    raw: dict[str, Any],
) -> McpRegistryInputField:
    argument_name = _normalize_text(raw.get("name"))
    label = argument_name or _normalize_text(raw.get("valueHint")) or f"arg_{index + 1}"
    return McpRegistryInputField(
        key=f"{source}:{index}:{argument_name or label}",
        label=label,
        source=source,
        required=bool(raw.get("isRequired")),
        secret=bool(raw.get("isSecret")),
        description=_normalize_text(raw.get("description")),
        default_value=raw.get("default"),
        format=_normalize_text(raw.get("format")) or "string",
        choices=_normalize_choices(raw.get("choices")),
        argument_name=argument_name,
        argument_mode=_normalize_argument_mode(raw),
        repeated=bool(raw.get("isRepeated")),
        value_hint=_normalize_text(raw.get("valueHint")),
    )


def _build_remote_header_field(index: int, raw: dict[str, Any]) -> McpRegistryInputField:
    name = _normalize_text(raw.get("name")) or f"header_{index + 1}"
    return McpRegistryInputField(
        key=f"header:{name}",
        label=name,
        source="header",
        required=bool(raw.get("isRequired")),
        secret=bool(raw.get("isSecret")),
        description=_normalize_text(raw.get("description")),
        default_value=raw.get("default"),
        format=_normalize_text(raw.get("format")) or "string",
        choices=_normalize_choices(raw.get("choices")),
        argument_name=name,
        argument_mode="named",
        value_hint=name,
    )


def _build_remote_variable_field(name: str, raw: dict[str, Any]) -> McpRegistryInputField:
    return McpRegistryInputField(
        key=f"url-variable:{name}",
        label=name,
        source="url-variable",
        required=bool(raw.get("isRequired")),
        secret=bool(raw.get("isSecret")),
        description=_normalize_text(raw.get("description")),
        default_value=raw.get("default"),
        format=_normalize_text(raw.get("format")) or "string",
        choices=_normalize_choices(raw.get("choices")),
        argument_name=name,
        argument_mode="named",
        value_hint=name,
    )


def _build_environment_field(index: int, raw: dict[str, Any]) -> McpRegistryInputField:
    name = _normalize_text(raw.get("name")) or f"env_{index + 1}"
    return McpRegistryInputField(
        key=f"environment:{name}",
        label=name,
        source="environment",
        required=bool(raw.get("isRequired")),
        secret=bool(raw.get("isSecret")),
        description=_normalize_text(raw.get("description")),
        default_value=raw.get("default"),
        format=_normalize_text(raw.get("format")) or "string",
        choices=_normalize_choices(raw.get("choices")),
        argument_name=name,
        argument_mode="named",
        value_hint=name,
    )


def _default_launcher_for_package(
    registry_type: str,
    runtime_hint: str,
) -> tuple[str, bool]:
    normalized_hint = _normalize_text(runtime_hint)
    normalized_registry_type = _normalize_text(registry_type).lower()
    if normalized_hint:
        return normalized_hint, True
    if normalized_registry_type == "npm":
        return "npx", True
    if normalized_registry_type == "pypi":
        return "uvx", True
    if normalized_registry_type == "oci":
        return "docker", True
    return "", False


def _build_package_option(index: int, server: dict[str, Any], raw: dict[str, Any]) -> McpRegistryInstallOption:
    transport = _normalize_transport((raw.get("transport") or {}).get("type"))
    registry_type = _normalize_text(raw.get("registryType")).lower()
    identifier = _normalize_text(raw.get("identifier"))
    version = _normalize_text(raw.get("version"))
    runtime_hint = _normalize_text(raw.get("runtimeHint"))
    runtime_command, supported = _default_launcher_for_package(registry_type, runtime_hint)
    if transport != "stdio":
        supported = False
        support_reason = (
            "当前内核还不支持“先起本地服务，再通过 HTTP 连接”的 MCP 目录条目自动安装。"
        )
    elif not supported:
        support_reason = "这个目录条目的启动器类型当前还没有自动安装规则。"
    else:
        support_reason = ""

    input_fields: list[McpRegistryInputField] = []
    for field_index, item in enumerate(raw.get("environmentVariables") or []):
        if isinstance(item, dict):
            input_fields.append(_build_environment_field(field_index, item))
    for field_index, item in enumerate(raw.get("runtimeArguments") or []):
        if isinstance(item, dict):
            input_fields.append(_build_argument_field("runtime-argument", field_index, item))
    for field_index, item in enumerate(raw.get("packageArguments") or []):
        if isinstance(item, dict):
            input_fields.append(_build_argument_field("package-argument", field_index, item))

    label_suffix = version or "latest"
    title = _display_title(server)
    return McpRegistryInstallOption(
        key=f"package:{index}:{hashlib.sha1(f'{registry_type}:{identifier}:{transport}'.encode('utf-8')).hexdigest()[:12]}",
        label=f"{title} / {registry_type or 'package'} / {label_suffix}",
        summary=f"{registry_type or 'package'} {identifier}".strip(),
        install_kind="package",
        transport=transport,
        supported=supported,
        support_reason=support_reason,
        registry_type=registry_type,
        identifier=identifier,
        version=version,
        runtime_command=runtime_command,
        input_fields=input_fields,
        url_template=_normalize_text((raw.get("transport") or {}).get("url")),
    )


def _build_remote_option(index: int, server: dict[str, Any], raw: dict[str, Any]) -> McpRegistryInstallOption:
    transport = _normalize_transport(raw.get("type"))
    headers = raw.get("headers") or []
    variables = raw.get("variables") or {}
    input_fields: list[McpRegistryInputField] = []
    for field_index, item in enumerate(headers):
        if isinstance(item, dict):
            input_fields.append(_build_remote_header_field(field_index, item))
    if isinstance(variables, dict):
        for key, item in variables.items():
            if isinstance(item, dict):
                input_fields.append(_build_remote_variable_field(str(key), item))
    url_template = _normalize_text(raw.get("url"))
    supported = bool(url_template)
    support_reason = "" if supported else "这个远程 MCP 条目没有提供可用的 URL。"
    title = _display_title(server)
    return McpRegistryInstallOption(
        key=f"remote:{index}:{hashlib.sha1(f'{transport}:{url_template}'.encode('utf-8')).hexdigest()[:12]}",
        label=f"{title} / remote / {transport}",
        summary=url_template or "remote MCP",
        install_kind="remote",
        transport=transport,
        supported=supported,
        support_reason=support_reason,
        url_template=url_template,
        input_fields=input_fields,
    )


def build_mcp_registry_install_options(server: dict[str, Any]) -> list[McpRegistryInstallOption]:
    options: list[McpRegistryInstallOption] = []
    for index, item in enumerate(server.get("packages") or []):
        if isinstance(item, dict):
            options.append(_build_package_option(index, server, item))
    for index, item in enumerate(server.get("remotes") or []):
        if isinstance(item, dict):
            options.append(_build_remote_option(index, server, item))
    return options


def _lookup_registry_client(
    *,
    server_name: str,
    suggested_client_key: str,
    installed_clients: dict[str, MCPClientConfig] | None,
) -> tuple[str | None, MCPClientConfig | None]:
    if not installed_clients:
        return None, None
    for key, client in installed_clients.items():
        registry = client.registry
        if registry is not None and registry.server_name == server_name:
            return key, client
    matched = installed_clients.get(suggested_client_key)
    if matched is not None:
        return suggested_client_key, matched
    return None, None


def _build_catalog_item(
    server: dict[str, Any],
    *,
    installed_clients: dict[str, MCPClientConfig] | None = None,
) -> McpRegistryCatalogItem:
    server_name = _normalize_text(server.get("name"))
    options = build_mcp_registry_install_options(server)
    category_keys = infer_mcp_registry_categories(server)
    transport_types = sorted({option.transport for option in options})
    suggested_client_key = _suggested_client_key(server_name)
    encoded_server_name = quote(server_name, safe="")
    matched_key, matched_client = _lookup_registry_client(
        server_name=server_name,
        suggested_client_key=suggested_client_key,
        installed_clients=installed_clients,
    )
    installed_version = ""
    installed_via_registry = False
    update_available = False
    if matched_client is not None and matched_client.registry is not None:
        installed_via_registry = matched_client.registry.server_name == server_name
        installed_version = _normalize_text(matched_client.registry.version)
        update_available = bool(
            installed_via_registry
            and installed_version
            and installed_version != _normalize_text(server.get("version"))
        )
    return McpRegistryCatalogItem(
        server_name=server_name,
        title=_display_title(server),
        description=_normalize_text(server.get("description")),
        version=_normalize_text(server.get("version")),
        source_url=_source_url(server_name),
        repository_url=_repository_url(server),
        website_url=_website_url(server),
        category_keys=category_keys,
        transport_types=transport_types,
        suggested_client_key=suggested_client_key,
        option_count=len(options),
        supported_option_count=sum(1 for option in options if option.supported),
        install_supported=any(option.supported for option in options),
        installed_client_key=matched_key,
        installed_via_registry=installed_via_registry,
        installed_version=installed_version,
        update_available=update_available,
        routes={
            "detail": f"/api/capability-market/mcp/catalog/{encoded_server_name}",
            "install": f"/api/capability-market/mcp/catalog/{encoded_server_name}/install",
        },
    )


def _server_matches_category(server: dict[str, Any], category: str) -> bool:
    if category == "all":
        return True
    categories = infer_mcp_registry_categories(server)
    return category in categories


def _list_url(*, query: str, cursor: str | None, limit: int) -> str:
    parts = [f"{_REGISTRY_BASE_URL}/v0/servers?limit={limit}"]
    if query:
        parts.append(f"search={quote(query)}")
    if cursor:
        parts.append(f"cursor={quote(cursor, safe='')}")
    return "&".join(parts)


def _detail_url(server_name: str) -> str:
    return (
        f"{_REGISTRY_BASE_URL}/v0/servers/"
        f"{quote(server_name, safe='')}/versions/latest"
    )


def _load_registry_list_page(*, query: str, cursor: str | None, limit: int) -> dict[str, Any]:
    payload = _registry_request(_list_url(query=query, cursor=cursor, limit=limit))
    return payload if isinstance(payload, dict) else {}


def _load_registry_server_detail(server_name: str) -> dict[str, Any]:
    payload = _registry_request(_detail_url(server_name))
    if not isinstance(payload, dict):
        return {}
    server = payload.get("server")
    return server if isinstance(server, dict) else {}


def _category_counts(items: list[McpRegistryCatalogItem]) -> list[McpRegistryCategory]:
    return list_mcp_registry_categories()


def search_mcp_registry_catalog(
    query: str = "",
    *,
    category: str = "all",
    cursor: str | None = None,
    limit: int = 12,
    installed_clients: dict[str, MCPClientConfig] | None = None,
) -> McpRegistryCatalogSearchResponse:
    normalized_query = _normalize_text(query)
    normalized_category = _normalize_category(category)
    normalized_limit = max(1, min(_LIST_LIMIT_CAP, int(limit or 12)))
    collected: list[McpRegistryCatalogItem] = []
    next_cursor = cursor
    warnings: list[str] = []
    fetch_rounds = 0

    while len(collected) < normalized_limit and fetch_rounds < _LIST_MAX_FETCH_ROUNDS:
        payload = _load_registry_list_page(
            query=normalized_query,
            cursor=next_cursor,
            limit=max(normalized_limit * 2, _LIST_FETCH_LIMIT),
        )
        servers = payload.get("servers")
        if not isinstance(servers, list):
            break
        for entry in servers:
            server = entry.get("server") if isinstance(entry, dict) else None
            if not isinstance(server, dict):
                continue
            if not _server_matches_category(server, normalized_category):
                continue
            collected.append(
                _build_catalog_item(server, installed_clients=installed_clients),
            )
            if len(collected) >= normalized_limit:
                break
        metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
        next_cursor = _normalize_text(metadata.get("nextCursor")) or None
        fetch_rounds += 1
        if not next_cursor:
            break

    if fetch_rounds >= _LIST_MAX_FETCH_ROUNDS and next_cursor:
        warnings.append("筛选结果较稀疏，只返回了当前能快速拉到的一页。")

    return McpRegistryCatalogSearchResponse(
        items=collected,
        categories=_category_counts(collected),
        cursor=cursor,
        next_cursor=next_cursor,
        has_more=bool(next_cursor),
        page_size=normalized_limit,
        warnings=warnings,
    )


def get_mcp_registry_catalog_detail(
    server_name: str,
    *,
    installed_clients: dict[str, MCPClientConfig] | None = None,
) -> McpRegistryCatalogDetailResponse:
    detail = _load_registry_server_detail(server_name)
    if not detail:
        raise ValueError(f"MCP registry server '{server_name}' not found")
    item = _build_catalog_item(detail, installed_clients=installed_clients)
    matched_registry_input_values: dict[str, Any] = {}
    if (
        item.installed_client_key
        and installed_clients is not None
        and item.installed_client_key in installed_clients
    ):
        registry = installed_clients[item.installed_client_key].registry
        if registry is not None and registry.server_name == server_name:
            matched_registry_input_values = dict(registry.input_values or {})
    return McpRegistryCatalogDetailResponse(
        item=item,
        install_options=build_mcp_registry_install_options(detail),
        categories=list_mcp_registry_categories(),
        matched_registry_client_key=item.installed_client_key,
        matched_registry_input_values=matched_registry_input_values,
    )


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    normalized = _normalize_text(value).lower()
    return normalized in {"1", "true", "yes", "on"}


def _resolve_field_value(
    field: McpRegistryInputField,
    provided_values: dict[str, Any],
) -> Any:
    if field.key in provided_values:
        return provided_values[field.key]
    if field.default_value not in (None, ""):
        return field.default_value
    if field.required:
        raise ValueError(f"Missing required field '{field.label}'")
    return None


def _explode_repeated_value(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, str):
        parts = [item.strip() for item in re.split(r"[\r\n,]+", value) if item.strip()]
        return parts if parts else [value]
    return [value]


def _render_argument_values(
    fields: list[McpRegistryInputField],
    provided_values: dict[str, Any],
) -> list[str]:
    args: list[str] = []
    for field in fields:
        value = _resolve_field_value(field, provided_values)
        if value is None or value == "":
            continue
        values = _explode_repeated_value(value) if field.repeated else [value]
        for item in values:
            if field.argument_mode == "flag":
                if _coerce_bool(item):
                    args.append(field.argument_name)
                continue
            if field.argument_mode == "named":
                args.append(field.argument_name)
                args.append(str(item))
                continue
            args.append(str(item))
    return args


def _materialize_remote_url(
    template: str,
    variables: list[McpRegistryInputField],
    provided_values: dict[str, Any],
) -> str:
    resolved = template
    for field in variables:
        value = _resolve_field_value(field, provided_values)
        if value in (None, ""):
            continue
        resolved = resolved.replace("{" + field.argument_name + "}", str(value))
    if "{" in resolved and "}" in resolved:
        raise ValueError("Remote MCP URL still contains unresolved variables")
    return resolved


def _materialize_headers(
    fields: list[McpRegistryInputField],
    provided_values: dict[str, Any],
) -> dict[str, str]:
    headers: dict[str, str] = {}
    for field in fields:
        value = _resolve_field_value(field, provided_values)
        if value in (None, ""):
            continue
        headers[field.argument_name] = str(value)
    return headers


def _materialize_environment(
    fields: list[McpRegistryInputField],
    provided_values: dict[str, Any],
) -> dict[str, str]:
    env: dict[str, str] = {}
    for field in fields:
        value = _resolve_field_value(field, provided_values)
        if value in (None, ""):
            continue
        env[field.argument_name] = str(value)
    return env


def _npm_package_ref(identifier: str, version: str) -> str:
    normalized_identifier = _normalize_text(identifier)
    normalized_version = _normalize_text(version)
    if not normalized_version:
        return normalized_identifier
    if normalized_identifier.endswith(f"@{normalized_version}"):
        return normalized_identifier
    return f"{normalized_identifier}@{normalized_version}"


def _pypi_package_ref(identifier: str, version: str) -> str:
    normalized_identifier = _normalize_text(identifier)
    normalized_version = _normalize_text(version)
    if not normalized_version or normalized_version == "latest":
        return normalized_identifier
    return f"{normalized_identifier}=={normalized_version}"


def _package_ref(option: McpRegistryInstallOption) -> str:
    if option.registry_type == "npm":
        return _npm_package_ref(option.identifier, option.version)
    if option.registry_type == "pypi":
        return _pypi_package_ref(option.identifier, option.version)
    return option.identifier


def _build_package_command_args(
    option: McpRegistryInstallOption,
    provided_values: dict[str, Any],
) -> tuple[str, list[str]]:
    runtime_fields = [field for field in option.input_fields if field.source == "runtime-argument"]
    package_fields = [field for field in option.input_fields if field.source == "package-argument"]
    runtime_args = _render_argument_values(runtime_fields, provided_values)
    package_args = _render_argument_values(package_fields, provided_values)
    command = option.runtime_command
    args: list[str] = []
    if option.registry_type == "npm":
        args.extend(["-y"])
        args.extend(runtime_args)
        args.append(_package_ref(option))
        args.extend(package_args)
        return command or "npx", args
    if option.registry_type == "pypi":
        args.extend(runtime_args)
        args.append(_package_ref(option))
        args.extend(package_args)
        return command or "uvx", args
    if option.registry_type == "oci":
        args.extend(["run", "--rm"])
        args.extend(runtime_args)
        args.append(_package_ref(option))
        args.extend(package_args)
        return command or "docker", args
    args.extend(runtime_args)
    args.append(_package_ref(option))
    args.extend(package_args)
    return command, args


def materialize_mcp_registry_install_plan(
    server_name: str,
    *,
    option_key: str,
    input_values: dict[str, Any] | None = None,
    client_key: str | None = None,
    enabled: bool = True,
    existing_client: MCPClientConfig | None = None,
) -> MaterializedMcpRegistryInstallPlan:
    detail = _load_registry_server_detail(server_name)
    if not detail:
        raise ValueError(f"MCP registry server '{server_name}' not found")
    options = build_mcp_registry_install_options(detail)
    option = next((item for item in options if item.key == option_key), None)
    if option is None:
        raise ValueError(f"Install option '{option_key}' not found for '{server_name}'")
    if not option.supported:
        raise ValueError(option.support_reason or "Selected install option is not supported")

    normalized_input_values = dict(input_values or {})
    resolved_client_key = _normalize_text(client_key) or _suggested_client_key(server_name)
    category_keys = infer_mcp_registry_categories(detail)
    title = _display_title(detail)

    if option.install_kind == "remote":
        header_fields = [field for field in option.input_fields if field.source == "header"]
        variable_fields = [field for field in option.input_fields if field.source == "url-variable"]
        url = _materialize_remote_url(option.url_template, variable_fields, normalized_input_values)
        headers = _materialize_headers(header_fields, normalized_input_values)
        client_config = MCPClientConfig(
            name=title,
            description=_normalize_text(detail.get("description")),
            enabled=enabled,
            transport=option.transport,
            url=url,
            headers=headers,
            command="",
            args=[],
            env={},
            cwd=existing_client.cwd if existing_client is not None else "",
            registry=MCPRegistryProvenance(
                server_name=server_name,
                version=_normalize_text(detail.get("version")),
                option_key=option.key,
                install_kind="remote",
                input_values=normalized_input_values,
                package_identifier="",
                package_registry_type="",
                remote_url=option.url_template,
                catalog_categories=category_keys,
            ),
        )
    else:
        env_fields = [field for field in option.input_fields if field.source == "environment"]
        command, args = _build_package_command_args(option, normalized_input_values)
        client_config = MCPClientConfig(
            name=title,
            description=_normalize_text(detail.get("description")),
            enabled=enabled,
            transport="stdio",
            url="",
            headers={},
            command=command,
            args=args,
            env=_materialize_environment(env_fields, normalized_input_values),
            cwd=existing_client.cwd if existing_client is not None else "",
            registry=MCPRegistryProvenance(
                server_name=server_name,
                version=_normalize_text(detail.get("version")),
                option_key=option.key,
                install_kind="package",
                input_values=normalized_input_values,
                package_identifier=option.identifier,
                package_registry_type=option.registry_type,
                remote_url="",
                catalog_categories=category_keys,
            ),
        )

    previous_version = (
        _normalize_text(existing_client.registry.version)
        if existing_client is not None and existing_client.registry is not None
        else ""
    )
    return MaterializedMcpRegistryInstallPlan(
        client_key=resolved_client_key,
        client=client_config,
        registry=client_config.registry or MCPRegistryProvenance(server_name=server_name),
        summary=f"{title} -> {option.label}",
        version_changed=bool(previous_version and previous_version != client_config.registry.version),
        previous_version=previous_version,
    )


class McpRegistryCatalog:
    """Thin service wrapper for official MCP registry read/write materialization."""

    def list_catalog(
        self,
        *,
        query: str = "",
        category: str = "all",
        cursor: str | None = None,
        limit: int = 12,
        installed_clients: dict[str, MCPClientConfig] | None = None,
    ) -> McpRegistryCatalogSearchResponse:
        return search_mcp_registry_catalog(
            query,
            category=category,
            cursor=cursor,
            limit=limit,
            installed_clients=installed_clients,
        )

    def get_catalog_detail(
        self,
        server_name: str,
        *,
        installed_clients: dict[str, MCPClientConfig] | None = None,
    ) -> McpRegistryCatalogDetailResponse:
        return get_mcp_registry_catalog_detail(
            server_name,
            installed_clients=installed_clients,
        )

    def materialize_install_plan(
        self,
        server_name: str,
        *,
        option_key: str,
        input_values: dict[str, Any] | None = None,
        client_key: str | None = None,
        enabled: bool = True,
        existing_client: MCPClientConfig | None = None,
    ) -> MaterializedMcpRegistryInstallPlan:
        return materialize_mcp_registry_install_plan(
            server_name,
            option_key=option_key,
            input_values=input_values,
            client_key=client_key,
            enabled=enabled,
            existing_client=existing_client,
        )
