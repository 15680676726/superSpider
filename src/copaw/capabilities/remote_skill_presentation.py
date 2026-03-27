# -*- coding: utf-8 -*-
"""Backend presentation helpers for remote skills."""
from __future__ import annotations

import re

_CJK_RE = re.compile(r"[\u4e00-\u9fff]")
_LEGACY_BRAND_TOKEN_RE = re.compile(r"\b(?:openclaw|copaw)\b", re.IGNORECASE)
_MOJIBAKE_MARKERS: tuple[str, ...] = (
    "Ã",
    "Â",
    "â",
    "Ð",
    "Ñ",
    "ä",
    "å",
    "æ",
    "ç",
    "é",
    "è",
)
_GENERIC_CHINESE_TITLE_PREFIXES: tuple[str, ...] = (
    "创建",
    "处理",
    "管理",
    "支持",
    "用于",
    "帮助",
    "通过",
    "设计",
    "控制",
    "查询",
    "自动执行",
    "自动化",
    "生成",
    "抓取",
)

_PRESET_PRESENTATIONS: dict[str, tuple[str, str]] = {
    "agent-browser": (
        "代理浏览器执行器",
        "通过结构化命令执行网页导航、点击、输入和页面快照。",
    ),
    "browser-automation": (
        "网页自动化助手",
        "自动执行网页登录、页面导航、表单填写、点击和数据提取。",
    ),
    "browser-use": (
        "网页自动化执行器",
        "处理网页登录、表单填写、截图采集和网页数据提取。",
    ),
    "crm": (
        "客户关系助手",
        "管理客户、联系人、跟进计划与销售线索。",
    ),
    "crm-manager": (
        "客户管理助手",
        "维护客户管道、跟进节点与本地 CRM 数据。",
    ),
    "customer-service-reply": (
        "客服回复模板",
        "生成常见问题、售前售后和评价回复的标准话术。",
    ),
    "dmm-ranking-lite": (
        "DMM 榜单轻采集",
        "抓取 DMM / FANZA 公开榜单并输出结构化排行结果。",
    ),
    "ecommerce": (
        "经营协同工具",
        "支撑目录维护、信息处理、价格跟踪和经营协同。",
    ),
    "ecommerce-price-comparison": (
        "价格比较工具",
        "比较多来源价格信息并输出差异结论。",
    ),
    "ecommerce-price-watcher": (
        "价格监控助手",
        "持续追踪价格变化、波动和预警信息。",
    ),
    "find-skills": (
        "技能发现助手",
        "帮助按任务发现、筛选并安装合适的远程技能包。",
    ),
    "google-calendar": (
        "日历协作助手",
        "处理日程安排、会议同步和时间协同。",
    ),
    "google-drive": (
        "云盘协作助手",
        "处理文件整理、共享协作和资料归档。",
    ),
    "github": (
        "GitHub 助手",
        "处理仓库、议题、拉取请求和 CI 运行等代码协作动作。",
    ),
    "gog": (
        "Google Workspace 协作助手",
        "连接 Gmail、日历、云盘、表格与文档等办公协作能力。",
    ),
    "image": (
        "图像处理工具",
        "处理图片格式、尺寸、压缩、元数据和平台适配。",
    ),
    "image-cog": (
        "图像创作助手",
        "生成创意素材、视觉内容和批量图像结果。",
    ),
    "image-ocr": (
        "图片识别工具",
        "从图片中提取文字并输出可继续处理的文本结果。",
    ),
    "jd-price-protect": (
        "价格保障助手",
        "批量检查记录是否存在价格保障机会并整理结果。",
    ),
    "ontology": (
        "知识图谱助手",
        "维护结构化记忆、实体关系和可组合知识对象。",
    ),
    "openmaic": (
        "OpenMAIC 安装引导",
        "提供 OpenMAIC 的拉取、配置和启动流程指导。",
    ),
    "automation-workflows": (
        "流程自动化工作台",
        "设计、编排并落地跨步骤自动化执行流程。",
    ),
    "content-strategy": (
        "内容策略助手",
        "规划内容主题、发布节奏和转化导向的内容动作。",
    ),
    "pinduoduo-listing": (
        "商品文案助手",
        "生成标题、说明、属性文案和回复建议。",
    ),
    "self-improving-agent": (
        "自我改进助手",
        "沉淀错误、修正和经验，持续回写可复用的改进结论。",
    ),
    "shopify": (
        "平台经营助手",
        "处理平台后台的目录、订单和运营协同动作。",
    ),
    "shopify-admin-api": (
        "平台管理助手",
        "管理订单、库存、退款和客户数据。",
    ),
    "sop-factory": (
        "SOP 生成工厂",
        "把粗略流程整理成标准作业流程、检查点与异常处理规范。",
    ),
    "summarize": (
        "内容总结助手",
        "总结网页、PDF、图片、音频和视频等内容。",
    ),
    "smart-customer-service-cn": (
        "智能客服助手",
        "承接中文客服问答、问题分流和回复辅助。",
    ),
    "vibesku": (
        "素材创意助手",
        "把素材加工成视觉内容和配套文案。",
    ),
}

_THEME_HINTS: tuple[tuple[str, tuple[str, ...], str], ...] = (
    ("网页自动化工具", ("browser", "web", "page", "site", "form", "login", "crawl", "scrape"), "自动执行网页登录、页面导航、表单填写与网页数据采集。"),
    ("图像与素材工具", ("image", "photo", "visual", "sku", "ocr", "design"), "处理图片、视觉素材、产品图和相关识别任务。"),
    ("表格数据工具", ("excel", "sheet", "spreadsheet", "csv"), "处理表格、结构化数据和批量数据整理任务。"),
    ("客户协作工具", ("crm", "contact", "customer", "lead", "sales"), "维护客户关系、线索流转和跟进流程。"),
    ("经营协同工具", ("ecommerce", "shop", "store", "listing", "price", "order", "inventory", "catalog", "shopify"), "支撑目录维护、价格跟踪、订单信息处理和经营协同。"),
    ("流程编排工具", ("workflow", "sop", "process", "runbook", "automation"), "整理流程、自动化执行链和标准作业步骤。"),
    ("研究监测工具", ("research", "monitor", "ranking", "trend", "signal", "benchmark"), "执行研究、监控、排行抓取和趋势分析。"),
    ("邮件协作工具", ("email", "mail", "gmail", "outlook"), "处理邮件收发、归档、搜索和协作跟进。"),
    ("代码协作工具", ("github", "git", "repo", "pull", "issue", "ci"), "处理代码仓库、议题、合并请求和自动化流水线。"),
    ("办公协作工具", ("calendar", "drive", "docs", "workspace"), "处理日历、文档、云盘和团队办公协作。"),
)

_TERM_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    ("ai-powered creative automation platform", "AI 创意自动化平台"),
    ("browser automation", "浏览器自动化"),
    ("capability", "能力"),
    ("checkpoints", "检查点"),
    ("chinese translation", "中文翻译"),
    ("daily/weekly/monthly", "日报/周报/月报"),
    ("detail page", "详情页"),
    ("exception handling", "异常处理"),
    ("fetch", "抓取"),
    ("guided sop", "引导式 SOP"),
    ("image generation", "图像生成"),
    ("inputs", "输入"),
    ("japanese title", "日文标题"),
    ("marketplace-ready copy", "可交付文案"),
    ("numbered text format", "编号文本格式"),
    ("outputs", "输出"),
    ("pricing strategy", "价格策略"),
    ("product sku photos", "素材图片"),
    ("professional e-commerce visuals", "专业视觉素材"),
    ("public rankings", "公开榜单"),
    ("review replies", "反馈回复"),
    ("review reply", "反馈回复"),
    ("roles", "角色"),
    ("rough workflows", "粗略流程"),
    ("setting up and using", "部署与使用"),
    ("standard operating procedures", "标准作业流程"),
    ("startup mode", "启动模式"),
    ("title optimization", "标题优化"),
    ("top 10", "前 10"),
    ("without api keys", "无需 API Key"),
)


def contains_cjk(value: str | None) -> bool:
    return bool(value and _CJK_RE.search(value))


def present_remote_skill_name(
    *,
    slug: str | None = None,
    name: str | None = None,
    summary: str | None = None,
    curated: bool = False,
) -> str:
    normalized_slug = _normalize_token(slug)
    normalized_name = _normalize_whitespace(name)
    normalized_summary = _normalize_whitespace(summary)
    if normalized_slug in _PRESET_PRESENTATIONS:
        return _PRESET_PRESENTATIONS[normalized_slug][0]
    cleaned_name = _strip_legacy_brand_tokens(normalized_name)
    if contains_cjk(cleaned_name):
        return cleaned_name or "远程技能包"
    if contains_cjk(normalized_summary):
        inferred = _infer_chinese_title(normalized_summary)
        if inferred:
            return inferred
    theme_label = _infer_theme_label(normalized_slug, normalized_name, normalized_summary)
    display_name = _beautify_identifier(cleaned_name or slug or "")
    if theme_label and display_name:
        return f"{theme_label}（{display_name}）"
    if theme_label:
        return theme_label
    if display_name:
        prefix = "SkillHub 精选" if curated else "远程技能包"
        return f"{prefix}（{display_name}）"
    return "远程技能包"


def present_remote_skill_summary(
    *,
    slug: str | None = None,
    name: str | None = None,
    summary: str | None = None,
) -> str:
    normalized_slug = _normalize_token(slug)
    normalized_summary = _normalize_whitespace(summary)
    if normalized_slug in _PRESET_PRESENTATIONS:
        return _PRESET_PRESENTATIONS[normalized_slug][1]
    chinese_line = _prefer_chinese_line(normalized_summary)
    if chinese_line:
        return chinese_line
    localized = localize_remote_skill_text(normalized_summary)
    if localized:
        return localized
    theme_summary = _infer_theme_summary(normalized_slug, name, normalized_summary)
    if theme_summary:
        return theme_summary
    return "来自 SkillHub 商店的远程技能包，可在安装后分配给指定智能体。"


def localize_remote_skill_text(value: str | None) -> str:
    text = _normalize_whitespace(value)
    if not text:
        return ""
    chinese_line = _prefer_chinese_line(text)
    if chinese_line:
        return chinese_line
    lowered = text.lower()
    for needle, replacement in _TERM_REPLACEMENTS:
        lowered = lowered.replace(needle, replacement)
    lowered = re.sub(r"\s{2,}", " ", lowered).strip()
    if contains_cjk(lowered):
        return lowered
    return lowered or text


def present_remote_skill_source_label(*, curated: bool = False) -> str:
    return "SkillHub 精选" if curated else "SkillHub 商店"


def _normalize_token(value: str | None) -> str:
    if not value:
        return ""
    return str(value).strip().lower().replace("_", "-")


def _normalize_whitespace(value: str | None) -> str:
    if not value:
        return ""
    text = _repair_likely_mojibake(str(value)).replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[^\S\n]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _looks_like_mojibake(value: str) -> bool:
    marker_hits = sum(value.count(marker) for marker in _MOJIBAKE_MARKERS)
    return marker_hits >= 2


def _repair_likely_mojibake(value: str) -> str:
    text = str(value or "")
    if not text or not _looks_like_mojibake(text):
        return text
    for source_encoding in ("latin-1", "cp1252"):
        try:
            repaired = text.encode(source_encoding).decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            continue
        if not repaired or repaired == text or _looks_like_mojibake(repaired):
            continue
        if contains_cjk(repaired) or any(char.isalpha() for char in repaired):
            return repaired
    return text


def _strip_legacy_brand_tokens(value: str | None) -> str:
    if not value:
        return ""
    stripped = _LEGACY_BRAND_TOKEN_RE.sub(" ", value)
    stripped = re.sub(r"[\(\)\[\]\-_/]+", " ", stripped)
    return _normalize_whitespace(stripped)


def _beautify_identifier(value: str) -> str:
    normalized = re.sub(r"[-_]+", " ", value or "").strip()
    normalized = re.sub(r"\s{2,}", " ", normalized)
    return normalized


def _prefer_chinese_line(value: str) -> str:
    if not value:
        return ""
    candidates = [
        part.strip(" -:;,.")
        for part in re.split(r"[\n\r]+", value)
        if part.strip()
    ]
    chinese_parts = [part for part in candidates if contains_cjk(part)]
    if chinese_parts:
        return chinese_parts[0]
    return ""


def _infer_chinese_title(summary: str) -> str:
    chinese_line = _prefer_chinese_line(summary)
    if not chinese_line:
        return ""
    candidate = re.split(r"[。；;，,:：\(\)]", chinese_line, maxsplit=1)[0].strip()
    if not candidate:
        return ""
    if any(
        candidate.startswith(prefix) and len(candidate) <= max(4, len(prefix) + 2)
        for prefix in _GENERIC_CHINESE_TITLE_PREFIXES
    ):
        return ""
    if len(candidate) > 18:
        return ""
    return candidate


def _infer_theme_label(*values: str | None) -> str:
    blob = " ".join(_normalize_token(value) for value in values if value).lower()
    for label, needles, _summary in _THEME_HINTS:
        if any(needle in blob for needle in needles):
            return label
    return ""


def _infer_theme_summary(*values: str | None) -> str:
    blob = " ".join(_normalize_token(value) for value in values if value).lower()
    for _label, needles, summary in _THEME_HINTS:
        if any(needle in blob for needle in needles):
            return summary
    return ""
