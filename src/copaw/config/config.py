# -*- coding: utf-8 -*-
import os
from typing import Optional, Union, Dict, List, Literal
from pydantic import BaseModel, Field, ConfigDict, model_validator

from ..providers.models import ModelSlotConfig
from ..constant import (
    HEARTBEAT_DEFAULT_EVERY,
    HEARTBEAT_DEFAULT_TARGET,
)


class BaseChannelConfig(BaseModel):
    """Base for channel config (read from config.json, no env)."""

    enabled: bool = False
    bot_prefix: str = ""
    filter_tool_messages: bool = False
    filter_thinking: bool = False
    dm_policy: Literal["open", "allowlist"] = "open"
    group_policy: Literal["open", "allowlist"] = "open"
    allow_from: List[str] = Field(default_factory=list)
    deny_message: str = ""


class IMessageChannelConfig(BaseChannelConfig):
    db_path: str = "~/Library/Messages/chat.db"
    poll_sec: float = 1.0
    media_dir: str = "~/.copaw/media"
    max_decoded_size: int = (
        10 * 1024 * 1024
    )  # 10MB default limit for Base64 data


class DiscordConfig(BaseChannelConfig):
    bot_token: str = ""
    http_proxy: str = ""
    http_proxy_auth: str = ""


class DingTalkConfig(BaseChannelConfig):
    client_id: str = ""
    client_secret: str = ""
    media_dir: str = "~/.copaw/media"


class FeishuConfig(BaseChannelConfig):
    """Feishu/Lark channel: app_id, app_secret; optional encrypt_key,
    verification_token for event handler. media_dir for received media.
    """

    app_id: str = ""
    app_secret: str = ""
    encrypt_key: str = ""
    verification_token: str = ""
    media_dir: str = "~/.copaw/media"


class QQConfig(BaseChannelConfig):
    app_id: str = ""
    client_secret: str = ""
    markdown_enabled: bool = True


class TelegramConfig(BaseChannelConfig):
    bot_token: str = ""
    http_proxy: str = ""
    http_proxy_auth: str = ""
    show_typing: Optional[bool] = None


class WeixinILinkConfig(BaseChannelConfig):
    bot_token: str = ""
    bot_token_file: str = "~/.qwenpaw/weixin_bot_token"
    base_url: str = ""
    media_dir: str = "~/.qwenpaw/media"
    group_reply_mode: Literal[
        "mention_or_prefix",
        "whitelist_full_open",
    ] = "mention_or_prefix"
    group_allowlist: List[str] = Field(default_factory=list)
    proactive_targets: List[str] = Field(default_factory=list)


class MQTTConfig(BaseChannelConfig):
    host: str = ""
    port: Optional[int] = None
    transport: str = ""
    clean_session: bool = True
    qos: int = 2
    username: Optional[str] = None
    password: Optional[str] = None
    subscribe_topic: str = ""
    publish_topic: str = ""
    tls_enabled: bool = False
    tls_ca_certs: Optional[str] = None
    tls_certfile: Optional[str] = None
    tls_keyfile: Optional[str] = None


class ConsoleConfig(BaseChannelConfig):
    """Console channel: prints agent responses to stdout."""

    enabled: bool = True


class VoiceChannelConfig(BaseChannelConfig):
    """Voice channel: Twilio ConversationRelay + Cloudflare Tunnel."""

    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    phone_number: str = ""
    phone_number_sid: str = ""
    tts_provider: str = "google"
    tts_voice: str = "en-US-Journey-D"
    stt_provider: str = "deepgram"
    language: str = "en-US"
    welcome_greeting: str = "Hi! This is Spider Mesh. How can I help you?"


class ChannelConfig(BaseModel):
    """Built-in channel configs; extra keys allowed for plugin channels."""

    model_config = ConfigDict(extra="allow")

    imessage: IMessageChannelConfig = IMessageChannelConfig()
    discord: DiscordConfig = DiscordConfig()
    dingtalk: DingTalkConfig = DingTalkConfig()
    feishu: FeishuConfig = FeishuConfig()
    qq: QQConfig = QQConfig()
    telegram: TelegramConfig = TelegramConfig()
    weixin_ilink: WeixinILinkConfig = WeixinILinkConfig()
    mqtt: MQTTConfig = MQTTConfig()
    console: ConsoleConfig = ConsoleConfig()
    voice: VoiceChannelConfig = VoiceChannelConfig()


class LastApiConfig(BaseModel):
    host: Optional[str] = None
    port: Optional[int] = None


class ActiveHoursConfig(BaseModel):
    """Optional active window for heartbeat (e.g. 08:00–22:00)."""

    start: str = "08:00"
    end: str = "22:00"


class HeartbeatConfig(BaseModel):
    """Heartbeat: run agent with HEARTBEAT.md as query at interval."""

    model_config = {"populate_by_name": True}

    enabled: bool = Field(default=False, description="Whether heartbeat is on")
    every: str = Field(default=HEARTBEAT_DEFAULT_EVERY)
    target: str = Field(default=HEARTBEAT_DEFAULT_TARGET)
    active_hours: Optional[ActiveHoursConfig] = Field(
        default=None,
        alias="activeHours",
    )


class AgentsDefaultsConfig(BaseModel):
    heartbeat: Optional[HeartbeatConfig] = None


class AgentsRunningConfig(BaseModel):
    """Agent runtime behavior configuration."""

    max_iters: int = Field(
        default=50,
        ge=1,
        description=(
            "Maximum number of reasoning-acting iterations for ReAct agent"
        ),
    )
    max_input_length: int = Field(
        default=128 * 1024,  # 128K = 131072 tokens
        ge=1000,
        description=(
            "Maximum input length (tokens) for the model context window"
        ),
    )
    memory_compact_ratio: float = Field(
        default=0.7,
        ge=0.01,
        le=0.99,
        description=("Ratio of memory to compact when memory is full"),
    )
    enable_tool_result_compact: bool = Field(
        default=False,
        description=("Whether to compact tool result messages in memory"),
    )
    tool_result_compact_keep_n: int = Field(
        default=5,
        ge=1,
        description=(
            "Number of tool result messages to keep in memory when compacting"
        ),
    )
    memory_compact_reserve: int = Field(
        default=10000,
        ge=1000,
        description=("Number of tokens to reserve in memory for tool results"),
    )

    @property
    def memory_compact_threshold(self) -> int:
        return int(self.max_input_length * self.memory_compact_ratio)


class AgentsLLMRoutingConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    enabled: bool = Field(default=False)
    mode: Literal["local_first", "cloud_first"] = Field(
        default="local_first",
        description=(
            "local_first routes to the local slot by default; cloud_first "
            "routes to the cloud slot by default. Smarter switching can be "
            "added later without changing the dual-slot config shape."
        ),
    )
    local: ModelSlotConfig = Field(
        default_factory=ModelSlotConfig,
        description="Local model slot (required when routing is enabled).",
    )
    cloud: Optional[ModelSlotConfig] = Field(
        default=None,
        description=(
            "Optional explicit cloud model slot; when null, uses "
            "providers.json active_llm."
        ),
    )


class AgentsConfig(BaseModel):
    defaults: AgentsDefaultsConfig = Field(
        default_factory=AgentsDefaultsConfig,
    )
    running: AgentsRunningConfig = Field(
        default_factory=AgentsRunningConfig,
    )
    llm_routing: AgentsLLMRoutingConfig = Field(
        default_factory=AgentsLLMRoutingConfig,
        description="LLM routing settings (local/cloud).",
    )
    language: str = Field(
        default="zh",
        description="Default runtime language for agent interactions (zh/en/ru)",
    )


class LastDispatchConfig(BaseModel):
    """Last channel/user/session that received a user-originated reply."""

    channel: str = ""
    user_id: str = ""
    session_id: str = ""


class MCPRegistryProvenance(BaseModel):
    """Official MCP registry provenance for installed clients."""

    source: Literal["official-mcp-registry"] = "official-mcp-registry"
    server_name: str = ""
    version: str = ""
    option_key: str = ""
    install_kind: Literal["package", "remote"] = "package"
    input_values: Dict[str, object] = Field(default_factory=dict)
    package_identifier: str = ""
    package_registry_type: str = ""
    remote_url: str = ""
    catalog_categories: List[str] = Field(default_factory=list)


class MCPClientConfig(BaseModel):
    """Configuration for a single MCP client."""

    model_config = ConfigDict(populate_by_name=True)

    name: str
    description: str = ""
    enabled: bool = True
    transport: Literal["stdio", "streamable_http", "sse"] = "stdio"
    url: str = ""
    headers: Dict[str, str] = Field(default_factory=dict)
    command: str = ""
    args: List[str] = Field(default_factory=list)
    env: Dict[str, str] = Field(default_factory=dict)
    cwd: str = ""
    registry: Optional[MCPRegistryProvenance] = None

    @model_validator(mode="before")
    @classmethod
    def _normalize_legacy_fields(cls, data):
        """Normalize common MCP field aliases from third-party examples."""
        if not isinstance(data, dict):
            return data

        payload = dict(data)

        if "isActive" in payload and "enabled" not in payload:
            payload["enabled"] = payload["isActive"]

        if "baseUrl" in payload and "url" not in payload:
            payload["url"] = payload["baseUrl"]

        if "type" in payload and "transport" not in payload:
            payload["transport"] = payload["type"]

        if (
            "transport" not in payload
            and (payload.get("url") or payload.get("baseUrl"))
            and not payload.get("command")
        ):
            payload["transport"] = "streamable_http"

        raw_transport = payload.get("transport")
        if isinstance(raw_transport, str):
            normalized = raw_transport.strip().lower()
            transport_alias_map = {
                "streamablehttp": "streamable_http",
                "http": "streamable_http",
                "stdio": "stdio",
                "sse": "sse",
            }
            payload["transport"] = transport_alias_map.get(
                normalized,
                normalized,
            )

        return payload

    @model_validator(mode="after")
    def _validate_transport_config(self):
        """Validate required fields for each MCP transport type."""
        if self.transport == "stdio":
            if not self.command.strip():
                raise ValueError("stdio MCP client requires non-empty command")
            return self

        if not self.url.strip():
            raise ValueError(
                f"{self.transport} MCP client requires non-empty url",
            )
        return self


class MCPConfig(BaseModel):
    """MCP clients configuration.

    Uses a dict to allow dynamic client definitions.
    Default tavily_search client is created and auto-enabled if API key exists.
    """

    clients: Dict[str, MCPClientConfig] = Field(
        default_factory=lambda: {
            "tavily_search": MCPClientConfig(
                name="tavily_mcp",
                # Auto-enable if TAVILY_API_KEY exists in environment
                enabled=bool(os.getenv("TAVILY_API_KEY")),
                command="npx",
                args=["-y", "tavily-mcp@latest"],
                env={"TAVILY_API_KEY": os.getenv("TAVILY_API_KEY", "")},
            ),
        },
    )


class ExternalCapabilityPackageConfig(BaseModel):
    """Config-backed external open-source capability mount."""

    capability_id: str
    name: str
    summary: str = ""
    enabled: bool = True
    kind: Literal["project-package", "adapter", "runtime-component"] = (
        "project-package"
    )
    source_kind: Literal["project", "adapter", "runtime"] = "project"
    source_url: str = ""
    package_ref: str = ""
    package_kind: str = "git-repo"
    package_version: str = ""
    execution_mode: Literal["shell"] = "shell"
    install_command: str = ""
    execute_command: str = ""
    healthcheck_command: str = ""
    runtime_kind: Literal["cli", "service"] | None = None
    supported_actions: List[str] = Field(default_factory=list)
    scope_policy: Literal["session", "work_context", "seat"] = "session"
    ready_probe_kind: str = "none"
    ready_probe_config: Dict[str, object] = Field(default_factory=dict)
    stop_strategy: str = "terminate"
    startup_entry_ref: str = ""
    intake_protocol_kind: str = "unknown"
    call_surface_ref: str = ""
    adapter_contract: Dict[str, object] = Field(default_factory=dict)
    environment_root: str = ""
    python_path: str = ""
    scripts_dir: str = ""
    environment_requirements: List[str] = Field(default_factory=list)
    evidence_contract: List[str] = Field(default_factory=lambda: ["shell-command"])
    provider_ref: str = "github"
    metadata: Dict[str, object] = Field(default_factory=dict)


class Config(BaseModel):
    """Root config (config.json)."""

    channels: ChannelConfig = ChannelConfig()
    mcp: MCPConfig = MCPConfig()
    external_capability_packages: Dict[str, ExternalCapabilityPackageConfig] = Field(
        default_factory=dict,
    )
    last_api: LastApiConfig = LastApiConfig()
    agents: AgentsConfig = Field(default_factory=AgentsConfig)
    last_dispatch: Optional[LastDispatchConfig] = None
    # When False, channel output hides tool call/result details (show "...").
    show_tool_details: bool = True


ChannelConfigUnion = Union[
    IMessageChannelConfig,
    DiscordConfig,
    DingTalkConfig,
    FeishuConfig,
    QQConfig,
    TelegramConfig,
    WeixinILinkConfig,
    MQTTConfig,
    ConsoleConfig,
    VoiceChannelConfig,
]
