# -*- coding: utf-8 -*-



from __future__ import annotations







import importlib







from .identity import EXECUTION_CORE_LEGACY_NAMES



from .service_context import *  # noqa: F401,F403











def search_hub_skills(*args, **kwargs):



    module = importlib.import_module("copaw.industry.service")



    return module.search_hub_skills(*args, **kwargs)











def search_curated_skill_catalog(*args, **kwargs):



    module = importlib.import_module("copaw.industry.service")



    return module.search_curated_skill_catalog(*args, **kwargs)











def _build_browser_match_signals(*args, **kwargs):



    module = importlib.import_module("copaw.industry.service_recommendation_pack")



    return module._build_browser_match_signals(*args, **kwargs)











def _build_desktop_match_signals(*args, **kwargs):



    module = importlib.import_module("copaw.industry.service_recommendation_pack")



    return module._build_desktop_match_signals(*args, **kwargs)











def _build_recommendation_reason_notes(*args, **kwargs):



    module = importlib.import_module("copaw.industry.service_recommendation_pack")



    return module._build_recommendation_reason_notes(*args, **kwargs)











def _hub_recommendation_output_limit(target_roles: list[IndustryRoleBlueprint]) -> int:



    return max(6, min(_HUB_RECOMMENDATION_MAX_ITEMS, max(1, len(target_roles)) * 2))











def _curated_recommendation_output_limit(target_roles: list[IndustryRoleBlueprint]) -> int:



    return max(4, min(_CURATED_RECOMMENDATION_MAX_ITEMS, max(1, len(target_roles)) * 2))







_BROWSER_DIRECT_TEXT_HINTS: tuple[tuple[str, str], ...] = (



    ("浏览器", "browser"),



    ("网页", "web page"),



    ("网站", "website"),



    ("站点", "website"),



    ("portal", "portal"),



    ("dashboard", "dashboard"),



    ("browser", "browser"),



    ("web", "web"),



    ("page", "page"),



    ("site", "site"),



    ("login", "login"),



    ("登录", "login"),



    ("表单", "form"),



    ("form", "form"),



)







_BROWSER_ACTION_HINTS: tuple[tuple[str, str], ...] = (



    ("访问", "visit"),



    ("打开网页", "open web"),



    ("登录", "login"),



    ("填写", "fill"),



    ("提交", "submit"),



    ("抓取", "scrape"),



    ("检索", "search"),



    ("搜索", "search"),



    ("crawl", "crawl"),



    ("scrape", "scrape"),



    ("search", "search"),



    ("submit", "submit"),



    ("fill", "fill"),



)







_HUB_QUERY_STOPWORDS = {



    "an",



    "and",



    "agent",



    "brief",



    "business",



    "build",



    "company",



    "core",



    "current",



    "customer",



    "design",



    "delivery",



    "draft",



    "evidence",



    "follow",



    "for",



    "from",



    "goal",



    "handle",



    "handles",



    "industry",



    "into",



    "lead",



    "manager",



    "market",



    "move",



    "next",



    "northwind",



    "operate",



    "operator",



    "operations",



    "own",



    "prepare",



    "ready",



    "recommendation",



    "research",



    "researcher",



    "review",



    "scope",



    "service",



    "services",



    "signal",



    "solution",



    "specialist",



    "support",



    "team",



    "the",



    "to",



    "use",



    "using",



    "with",



    "workflows",



}







_ROLE_CAPABILITY_FAMILY_RULES: tuple[tuple[str, str, str, tuple[str, ...]], ...] = (



    (



        "browser",



        "网页执行",



        "browser",



        (



            "browser",



            "web",



            "page",



            "site",



            "portal",



            "dashboard",



            "login",



            "form",



            "browser_use",



            "网页",



            "网站",



            "页面",



            "登录",



            "表单",



            "抓取",



        ),



    ),



    (


        "desktop",


        "桌面执行",


        "desktop",


        (


            "desktop",


            "windows",


            "win32",


            "native app",


            "desktop app",


            "desktop client",


            "local client",


            "桌面",


            "桌面应用",


            "桌面软件",


            "桌面客户端",


            "本地客户端",


            "本地应用",


            "原生应用",


            "窗口",


            "键盘",


            "鼠标",


        ),


    ),


    (



        "research",



        "研究分析",



        "research",



        (



            "research",



            "monitor",



            "analysis",



            "insight",



            "trend",



            "signal",



            "benchmark",



            "研究",



            "调研",



            "监测",



            "分析",



            "趋势",



            "情报",



            "竞品",



        ),



    ),



    (



        "workflow",



        "流程编排",



        "workflow",



        (



            "workflow",



            "process",



            "sop",



            "automation",



            "runbook",



            "solution",



            "planning",



            "design",



            "流程",



            "自动化",



            "编排",



            "SOP",



            "方案",



            "规划",



            "设计",



        ),



    ),



    (



        "content",



        "内容产出",



        "content",



        (



            "content",



            "copy",



            "writing",



            "document",



            "docs",



            "ppt",



            "summary",



            "内容",



            "文案",



            "写作",



            "稿件",



            "总结",



            "汇总",



        ),



    ),



    (



        "image",



        "图像素材",



        "image",



        (



            "image",



            "visual",



            "photo",



            "ocr",



            "design",



            "图片",



            "图像",



            "素材",



            "视觉",



            "识别",



        ),



    ),



    (


        "data",


        "数据表格",


        "spreadsheet",


        (


            "sheet",


            "spreadsheet",


            "csv",


            "table",


            "data",


            "表格",



            "数据",



            "台账",



        ),



    ),



    (



        "crm",



        "客户协作",



        "crm",



        (


            "crm",


            "customer",


            "contact",


            "lead",


            "sales",


            "account",


            "pipeline",


            "客户",


            "线索",


            "销售",


            "跟进",


        ),


    ),



    (



        "email",



        "邮件协作",



        "email",



        (


            "email",


            "mail",


            "inbox",


            "reply",


            "thread",


            "邮件",


            "邮箱",


        ),


    ),


    (



        "github",



        "代码协作",



        "github",



        (



            "github",



            "git",



            "repo",



            "pull request",



            "issue",



            "ci",



            "代码",



            "仓库",



            "提交",



        ),



    ),



)







_CAPABILITY_FAMILY_SEARCH_QUERIES: dict[str, tuple[str, ...]] = {


    "browser": ("browser automation", "browser"),


    "desktop": ("desktop automation", "desktop"),


    "research": ("industry research", "research"),


    "workflow": ("workflow automation", "workflow"),


    "content": ("content strategy", "content"),


    "image": ("image", "ocr"),


    "data": ("spreadsheet automation", "data analysis"),


    "crm": ("customer service", "crm"),


    "email": ("email automation", "email"),


    "github": ("github", "git workflow"),


}






_EXECUTION_CORE_ALLOWED_CAPABILITY_FAMILIES: tuple[str, ...] = (



    "workflow",



    "research",



    "content",



)







_EXECUTION_CORE_BLOCKED_CAPABILITY_FAMILIES: tuple[str, ...] = (



    "browser",



    "desktop",



    "crm",



    "email",



    "image",



    "data",



    "github",



)







_ROLE_SIGNAL_BUCKET_WEIGHTS: dict[str, int] = {



    "explicit-skill": 11,



    "role-contract": 8,



    "history-task": 7,



    "output-target": 7,



    "environment-type": 6,



    "profile-context": 3,



}







_GENERIC_ROLE_LABEL_HINTS = (



    "solution lead",



    "solution specialist",



    "solution operator",



    "solution planner",



    "solution",



    "specialist",



    "operator",



    "operations specialist",



    "operations lead",



    "business specialist",



    "business operator",



    "delivery specialist",



    "delivery lead",



    "assistant",



    "业务专员",



    "执行专员",



    "运营专员",



    "方案专员",



    "方案负责人",



    "交付专员",



    "助理",



)







_ROLE_LABEL_REFINEMENT_RULES: tuple[



    tuple[str, frozenset[str], tuple[str, ...]],



    ...,



] = (



    (



        "店铺运营",



        frozenset({"browser", "crm", "content", "workflow"}),



        (



            "store",



            "shop",



            "merchant",



            "marketplace",



            "listing",



            "sku",



            "order",



            "fulfillment",



            "店铺",



            "商城",



            "电商",



            "商品",



            "订单",



            "履约",



            "平台运营",



        ),



    ),



    (



        "客户运营",



        frozenset({"crm", "email", "desktop", "browser"}),



        (


            "customer service",


            "customer success",


            "customer follow",


            "crm",


            "lead",


            "account",


            "pipeline",


            "客户",


            "客服",


            "线索",


            "跟进",


            "售后",



            "客户成功",



        ),



    ),



    (



        "内容运营",



        frozenset({"content", "image"}),



        (



            "content",



            "copy",



            "article",



            "social",



            "post",



            "video",



            "script",



            "内容",



            "文案",



            "文章",



            "社媒",



            "视频",



            "脚本",



        ),



    ),



    (


        "数据分析",


        frozenset({"data"}),


        (


            "report",


            "analysis",


            "dashboard",


            "sheet",


            "spreadsheet",


            "kpi",


            "metric",


            "数据",


            "分析",


            "报表",



            "指标",



            "复盘",



            "表格",



        ),



    ),



    (


        "桌面交付",


        frozenset({"desktop"}),


        (


            "desktop",


            "windows",


            "native app",


            "desktop app",


            "desktop client",


            "local client",


            "桌面",


            "桌面客户端",


            "本地客户端",


            "本地应用",


            "窗口",


            "键盘",


        ),


    ),


    (



        "平台实施",



        frozenset({"browser", "workflow"}),



        (



            "onboarding",



            "implementation",



            "setup",



            "configure",



            "configuration",



            "portal",



            "dashboard",



            "form",



            "login",



            "实施",



            "开通",



            "配置",



            "部署",



            "集成",



            "表单",



            "登录",



        ),



    ),



    (



        "流程设计",



        frozenset({"workflow"}),



        (



            "solution",



            "design",



            "planning",



            "workflow",



            "process",



            "sop",



            "automation",



            "方案",



            "设计",



            "规划",



            "流程",



            "自动化",



            "编排",



        ),



    ),



)







_ROLE_LABEL_REFINEMENT_FALLBACKS = {



    "crm": "客户运营",



    "content": "内容运营",



    "data": "数据分析",



    "desktop": "桌面交付",



    "browser": "平台实施",



    "workflow": "流程运营",



    "email": "邮件协同",



    "github": "工程协作",



    "image": "视觉素材",



    "research": "研究分析",



}











@dataclass(frozen=True, slots=True)



class _SkillHubQueryCandidate:



    query: str



    kind: str



    family_id: str | None = None







_CHAT_WRITEBACK_ROLE_SIGNAL_HINTS: tuple[



    tuple[tuple[str, ...], tuple[str, ...]],



    ...,



] = (



    (



        ("researcher", "research", "analyst", "insight"),



        (



            "研究",



            "调研",



            "分析",



            "监控",



            "巡检",



            "竞品",



            "同行",



            "情报",



            "趋势",



            "数据",



            "线索",



            "research",



            "analysis",



            "analyze",



            "monitor",



            "monitoring",



            "signal",



            "signals",



            "scan",



            "insight",



            "competitor",



            "competitors",



            "benchmark",



        ),



    ),



    (



        ("solution", "architect", "design", "planner", "planning"),



        (



            "方案",



            "设计",



            "规划",



            "流程",



            "架构",



            "scope",



            "solution",



            "design",



            "planning",



            "workflow",



            "architecture",



        ),



    ),



    (



        ("enablement", "onboarding", "training", "rollout", "deployment"),



        (



            "启用",



            "部署",



            "落地",



            "培训",



            "试点",



            "交付",



            "pilot",



            "rollout",



            "enablement",



            "onboarding",



            "deployment",



            "training",



            "adoption",



        ),



    ),



    (



        ("ops", "operation", "operations", "operator", "delivery"),



        (



            "运营",



            "执行",



            "交付",



            "运维",



            "操作",



            "process",



            "operations",



            "execution",



            "delivery",



            "runbook",



        ),



    ),



)







_CHAT_WRITEBACK_ROUTING_STOPWORDS = {



    *list(_HUB_QUERY_STOPWORDS),



    "agent",



    "agentic",



    "industry",



    "operating",



    "owner",



    "role",



    "system",



    "task",



    "team",



    "执行中枢",



    "Spider Mesh",



    *(alias.replace("执行中枢", "").strip() for alias in EXECUTION_CORE_LEGACY_NAMES),



}











def _utc_now() -> datetime:



    return datetime.now(timezone.utc)











def _string(value: object | None) -> str | None:



    if value is None:



        return None



    text = str(value).strip()



    return text or None











def _mapping(value: object | None) -> dict[str, object]:



    if isinstance(value, dict):



        return value



    return {}











def _parse_datetime(value: object | None) -> datetime | None:



    if isinstance(value, datetime):



        if value.tzinfo is None or value.utcoffset() is None:



            return value.replace(tzinfo=timezone.utc)



        return value.astimezone(timezone.utc)



    if not isinstance(value, str):



        return None



    raw = value.strip()



    if not raw:



        return None



    if raw.endswith("Z"):



        raw = f"{raw[:-1]}+00:00"



    try:



        parsed = datetime.fromisoformat(raw)



    except ValueError:



        return None



    if parsed.tzinfo is None or parsed.utcoffset() is None:



        parsed = parsed.replace(tzinfo=timezone.utc)



    return parsed.astimezone(timezone.utc)











def _sort_timestamp(value: object | None) -> datetime:



    return _parse_datetime(value) or datetime.min.replace(tzinfo=timezone.utc)











def _filter_since(



    items: list[dict[str, Any]],



    key: str,



    since: datetime,



) -> list[dict[str, Any]]:



    filtered = [



        item



        for item in items



        if (_parse_datetime(item.get(key)) or datetime.min.replace(tzinfo=timezone.utc))



        >= since



    ]



    filtered.sort(key=lambda item: _sort_timestamp(item.get(key)), reverse=True)



    return filtered











def _unique_strings(*values: object) -> list[str]:



    seen: set[str] = set()



    items: list[str] = []



    for value in values:



        if isinstance(value, str):



            normalized = value.strip()



            if normalized and normalized not in seen:



                seen.add(normalized)



                items.append(normalized)



            continue



        if not isinstance(value, list):



            continue



        for entry in value:



            if not isinstance(entry, str):



                continue



            normalized = entry.strip()



            if not normalized or normalized in seen:



                continue



            seen.add(normalized)



            items.append(normalized)



    return items











def _normalize_search_phrase(value: object | None) -> str:



    text = _string(value) or ""



    if not text:



        return ""



    normalized = text.replace("_", " ")



    normalized = re.sub(r"[-/|]+", " ", normalized)



    normalized = re.sub(r"\b[a-z0-9]{4,}(?:-[a-z0-9]{2,}){2,}\b", " ", normalized)



    normalized = re.sub(r"\s{2,}", " ", normalized).strip()



    if not normalized:



        return ""



    if re.search(r"[\u4e00-\u9fff]", normalized):



        return normalized[:24].strip()



    words = normalized.split()



    if len(words) > 6:



        normalized = " ".join(words[:6])



    return normalized.strip()











def _append_query_candidate(



    candidates: list[_SkillHubQueryCandidate],



    seen_queries: set[str],



    *,



    query: str | None,



    kind: str,



    family_id: str | None = None,



) -> None:



    normalized = _normalize_search_phrase(query)



    if not normalized:



        return



    dedupe_key = normalized.lower()



    if dedupe_key in seen_queries:



        return



    seen_queries.add(dedupe_key)



    candidates.append(



        _SkillHubQueryCandidate(



            query=normalized,



            kind=kind,



            family_id=family_id,



        )



    )











def _sequence_intersects(values: object, candidates: set[str]) -> bool:



    if not candidates or not isinstance(values, (list, tuple, set)):



        return False



    for entry in values:



        normalized = _string(entry)



        if normalized and normalized in candidates:



            return True



    return False











def _search_blob(values: list[str]) -> str:



    return "\n".join(value.strip().lower() for value in values if value and value.strip())











def _match_keyword_labels(
    blob: str,
    hints: tuple[tuple[str, str], ...],
) -> list[str]:
    matched: list[str] = []
    seen: set[str] = set()
    if not blob:
        return matched
    for needle, label in hints:
        normalized = needle.strip().lower()
        if (
            not normalized
            or not _blob_contains_keyword_hint(blob, normalized)
            or label in seen
        ):
            continue
        matched.append(label)
        seen.add(label)
    return matched


def _blob_contains_keyword_hint(blob: str, needle: str) -> bool:
    if not blob or not needle:
        return False
    if re.search(r"[一-鿿]", needle):
        return needle in blob
    if re.fullmatch(r"[a-z0-9]+(?: [a-z0-9]+)*", needle):
        pattern = (
            r"(?<![a-z0-9])"
            + re.escape(needle).replace(r"\ ", r"\s+")
            + r"(?![a-z0-9])"
        )
        return re.search(pattern, blob) is not None
    return needle in blob


def _tokenize_capability_hint(value: str) -> set[str]:



    normalized = value.strip().lower()



    if not normalized:



        return set()



    ascii_tokens = {



        token



        for token in re.split(r"[^a-z0-9]+", normalized)



        if token



    }



    # Extract Chinese character sequences (2+ chars) as tokens



    chinese_tokens = {



        match



        for match in re.findall(r"[\u4e00-\u9fff]{2,}", normalized)



    }



    return ascii_tokens | chinese_tokens











def _skill_capability_id(skill_name: str | None) -> str:



    normalized = _string(skill_name) or ""



    return f"skill:{normalized}" if normalized else ""











def _extract_search_terms(



    values: list[str],



    *,



    limit: int = 8,



) -> list[str]:



    terms: list[str] = []



    seen: set[str] = set()



    for value in values:



        # Extract ASCII tokens



        for token in re.findall(r"[a-z0-9][a-z0-9_-]{1,31}", value.lower()):



            if token in _HUB_QUERY_STOPWORDS or token in seen:



                continue



            seen.add(token)



            terms.append(token)



            if len(terms) >= limit:



                return terms



        # Extract Chinese character sequences (2+ chars) as tokens



        for token in re.findall(r"[\u4e00-\u9fff]{2,}", value):



            if token in _HUB_QUERY_STOPWORDS or token in seen:



                continue



            seen.add(token)



            terms.append(token)



            if len(terms) >= limit:



                return terms



    return terms











def _role_explicit_skill_names(role: IndustryRoleBlueprint) -> list[str]:



    return [



        capability.split(":", 1)[1].strip()



        for capability in role.allowed_capabilities



        if capability.strip().lower().startswith("skill:")



    ]











def _role_context_signal_buckets(



    *,



    profile: IndustryProfile,



    role: IndustryRoleBlueprint,



    goal_context: list[str],



) -> list[tuple[str, list[str]]]:



    explicit_skill_names = _role_explicit_skill_names(role)



    return [



        ("explicit-skill", explicit_skill_names),



        (



            "role-contract",



            _unique_strings(



                role.role_id,



                role.goal_kind,



                role.name,



                role.role_name,



                role.role_summary,



                role.mission,



                list(role.allowed_capabilities or []),



            ),



        ),



        (



            "history-task",



            _unique_strings(



                goal_context,



                list(profile.operator_requirements or []),



                profile.experience_notes,



            ),



        ),



        (



            "output-target",



            _unique_strings(



                list(role.evidence_expectations or []),



                list(profile.goals or []),



            ),



        ),



        (



            "environment-type",



            _unique_strings(



                list(role.environment_constraints or []),



                list(profile.channels or []),



                list(profile.constraints or []),



                profile.business_model,



                profile.region,



            ),



        ),



        (



            "profile-context",



            _unique_strings(



                profile.industry,



                profile.sub_industry,



                profile.product,



                list(profile.target_customers or []),



                profile.budget_summary,



                profile.notes,



            ),



        ),



    ]











def _role_search_values(



    *,



    profile: IndustryProfile,



    role: IndustryRoleBlueprint,



    goal_context: list[str],



) -> list[str]:



    values: list[str] = []



    for _bucket_id, bucket_values in _role_context_signal_buckets(



        profile=profile,



        role=role,



        goal_context=goal_context,



    ):



        values.extend(bucket_values)



    return _unique_strings(values)











def _role_signal_bucket_weight(bucket_id: str) -> int:



    return _ROLE_SIGNAL_BUCKET_WEIGHTS.get(bucket_id, 1)











def _capability_family_synergy_score(bucket_matches: dict[str, int]) -> int:



    matched_buckets = set(bucket_matches)



    if not matched_buckets:



        return 0



    synergy = 0



    if len(matched_buckets) >= 2:



        synergy += (len(matched_buckets) - 1) * 2



    if {"history-task", "environment-type"}.issubset(matched_buckets):



        synergy += 4



    if {"history-task", "output-target"}.issubset(matched_buckets):



        synergy += 5



    if {"environment-type", "output-target"}.issubset(matched_buckets):



        synergy += 4



    if "role-contract" in matched_buckets and (



        "history-task" in matched_buckets or "output-target" in matched_buckets



    ):



        synergy += 3



    strong_match_count = sum(1 for strength in bucket_matches.values() if strength >= 2)



    if strong_match_count >= 2:



        synergy += strong_match_count



    return synergy











def _capability_family_rule(



    family_id: str,



) -> tuple[str, str, str, tuple[str, ...]] | None:



    for rule in _ROLE_CAPABILITY_FAMILY_RULES:



        if rule[0] == family_id:



            return rule



    return None











def _capability_family_label(family_id: str) -> str:



    rule = _capability_family_rule(family_id)



    return rule[1] if rule is not None else family_id











def _capability_family_query(family_id: str) -> str:



    queries = _CAPABILITY_FAMILY_SEARCH_QUERIES.get(family_id)



    if queries:



        return queries[0]



    rule = _capability_family_rule(family_id)



    return rule[2] if rule is not None else family_id











def _capability_family_queries(family_id: str) -> tuple[str, ...]:



    queries = _CAPABILITY_FAMILY_SEARCH_QUERIES.get(family_id)



    if queries:



        return queries



    rule = _capability_family_rule(family_id)



    if rule is None:



        return (family_id,)



    return (rule[2],)











def _capability_family_primary_terms(family_id: str) -> list[str]:



    rule = _capability_family_rule(family_id)



    if rule is None:



        return [family_id]



    family_id, label, query, _hints = rule



    return _unique_strings(



        family_id,



        label,



        query,



        list(_capability_family_queries(family_id)),



    )











def _capability_family_hint_terms(family_id: str) -> list[str]:



    rule = _capability_family_rule(family_id)



    if rule is None:



        return []



    return _unique_strings(list(rule[3]))











def _capability_family_labels(family_ids: list[str]) -> list[str]:



    return [_capability_family_label(family_id) for family_id in family_ids]











def _family_needle_matches_blob(needle: str, blob: str) -> bool:



    normalized = re.sub(r"[-_/]+", " ", str(needle or "").strip().lower())



    haystack = re.sub(r"[-_/]+", " ", str(blob or "").lower())



    if not normalized or not haystack:



        return False



    if re.search(r"[\u4e00-\u9fff]", normalized):



        return normalized in haystack



    if len(normalized) <= 3:



        pattern = rf"(?<![a-z0-9]){re.escape(normalized)}(?![a-z0-9])"



        return re.search(pattern, haystack) is not None



    return normalized in haystack











def _infer_role_capability_family_ids_from_values(*values: object) -> list[str]:



    blob = _search_blob(_unique_strings(*values))



    if not blob:



        return []



    matched: list[str] = []



    for family_id, _label, _query, _hints in _ROLE_CAPABILITY_FAMILY_RULES:



        primary_terms = _capability_family_primary_terms(family_id)



        if any(_family_needle_matches_blob(term, blob) for term in primary_terms):



            matched.append(family_id)



            continue



        if any(



            _family_needle_matches_blob(str(needle), blob)



            for needle in _capability_family_hint_terms(family_id)



        ):



            matched.append(family_id)



    return _unique_strings(matched)











def _explicit_role_capability_family_ids(role: IndustryRoleBlueprint) -> list[str]:



    normalized: list[str] = []



    seen: set[str] = set()



    for raw in role.preferred_capability_families:



        value = _string(raw)



        if not value:



            continue



        family_id = next(



            (



                candidate



                for candidate, _label, _query, _hints in _ROLE_CAPABILITY_FAMILY_RULES



                if any(



                    _normalize_search_phrase(term).lower()



                    == _normalize_search_phrase(value).lower()



                    for term in _capability_family_primary_terms(candidate)



                )



            ),



            None,



        )



        if family_id is None:



            inferred = _infer_role_capability_family_ids_from_values([value])



            family_id = inferred[0] if len(inferred) == 1 else None



        if family_id is None or family_id in seen:



            continue



        seen.add(family_id)



        normalized.append(family_id)



    return normalized











def _role_capability_family_scores(



    *,



    profile: IndustryProfile,



    role: IndustryRoleBlueprint,



    goal_context: list[str],



) -> dict[str, int]:



    signal_buckets = _role_context_signal_buckets(



        profile=profile,



        role=role,



        goal_context=goal_context,



    )



    candidate_family_ids = (



        list(_EXECUTION_CORE_ALLOWED_CAPABILITY_FAMILIES)



        if is_execution_core_role_id(role.role_id)



        else [family_id for family_id, _label, _query, _hints in _ROLE_CAPABILITY_FAMILY_RULES]



    )



    scores: dict[str, int] = {}



    for family_id in candidate_family_ids:



        score = 0



        primary_terms = _capability_family_primary_terms(family_id)



        hint_terms = _capability_family_hint_terms(family_id)



        bucket_matches: dict[str, int] = {}



        for bucket_id, values in signal_buckets:



            weight = _role_signal_bucket_weight(bucket_id)



            for value in values:



                blob = _search_blob([value])



                if not blob:



                    continue



                if any(_family_needle_matches_blob(term, blob) for term in primary_terms):



                    score += weight * 2



                    bucket_matches[bucket_id] = 2



                    break



                if any(



                    _family_needle_matches_blob(str(needle), blob)



                    for needle in hint_terms



                ):



                    score += weight



                    bucket_matches.setdefault(bucket_id, 1)



                    break



        score += _capability_family_synergy_score(bucket_matches)



        if score > 0:



            scores[family_id] = score



    return scores











def _select_scored_capability_family_ids(scores: dict[str, int]) -> list[str]:



    ordered = sorted(



        scores.items(),



        key=lambda item: (-item[1], item[0]),



    )



    if not ordered:



        return []



    selected = [ordered[0][0]]



    if len(ordered) == 1:



        return selected



    primary_score = ordered[0][1]



    secondary_family_id, secondary_score = ordered[1]



    if secondary_score < _ROLE_CAPABILITY_SECONDARY_MIN_SCORE:



        return selected



    if (



        secondary_score < int(primary_score * _ROLE_CAPABILITY_SECONDARY_MIN_RATIO)



        and (primary_score - secondary_score) > _ROLE_CAPABILITY_SECONDARY_MAX_GAP



    ):



        return selected



    selected.append(secondary_family_id)



    return selected[:_ROLE_CAPABILITY_MAX_SELECTED_FAMILIES]











def _execution_core_capability_family_ids(



    *,



    profile: IndustryProfile,



    role: IndustryRoleBlueprint,



    goal_context: list[str],



) -> list[str]:



    explicit = [



        family_id



        for family_id in _explicit_role_capability_family_ids(role)



        if family_id in _EXECUTION_CORE_ALLOWED_CAPABILITY_FAMILIES



    ]



    if explicit:



        return _unique_strings(["workflow"], explicit)[:3]



    scores = _role_capability_family_scores(



        profile=profile,



        role=role,



        goal_context=goal_context,



    )



    selected = [



        family_id



        for family_id in _select_scored_capability_family_ids(scores)



        if family_id in _EXECUTION_CORE_ALLOWED_CAPABILITY_FAMILIES



    ]



    inferred = [



        family_id



        for family_id in _infer_role_capability_family_ids_from_values(



            _role_search_values(



                profile=profile,



                role=role,



                goal_context=goal_context,



            )



        )



        if family_id in _EXECUTION_CORE_ALLOWED_CAPABILITY_FAMILIES



    ]



    return _unique_strings(["workflow"], selected, inferred)[:3]











def _role_capability_family_ids(



    *,



    profile: IndustryProfile,



    role: IndustryRoleBlueprint,



    goal_context: list[str],



) -> list[str]:



    if is_execution_core_role_id(role.role_id):



        return _execution_core_capability_family_ids(



            profile=profile,



            role=role,



            goal_context=goal_context,



        )



    explicit = _explicit_role_capability_family_ids(role)



    if explicit:



        return explicit



    scores = _role_capability_family_scores(



        profile=profile,



        role=role,



        goal_context=goal_context,



    )



    return _select_scored_capability_family_ids(scores)











def _role_needs_positioning_refinement(role: IndustryRoleBlueprint) -> bool:



    if is_execution_core_role_id(role.role_id) or role.role_id == "researcher":



        return False



    label = _normalize_search_phrase(role.role_name or role.name)



    if not label:



        return False



    return any(



        _family_needle_matches_blob(candidate, label)



        for candidate in _GENERIC_ROLE_LABEL_HINTS



    )











def _role_context_matches_keywords(blob: str, keywords: tuple[str, ...]) -> bool:



    return any(_family_needle_matches_blob(keyword, blob) for keyword in keywords)











def _suggest_precise_role_label(



    *,



    profile: IndustryProfile,



    role: IndustryRoleBlueprint,



    goal_context: list[str],



    family_ids: list[str],



) -> str | None:



    if not family_ids:



        return None



    context_blob = _search_blob(



        _role_search_values(



            profile=profile,



            role=role,



            goal_context=goal_context,



        ),



    )



    family_set = set(family_ids)



    primary_family = family_ids[0]







    def rule_priority(



        rule: tuple[str, frozenset[str], tuple[str, ...]],



    ) -> tuple[int, int]:



        label, supported_families, _keywords = rule



        if label == "店铺运营" and (family_set & {"browser", "crm", "content", "workflow"}):



            return (0, 0)



        if primary_family == "desktop":



            if label == "桌面交付":



                return (0, 0)



            if label == "客户运营":



                return (2, 0)



        if primary_family == "browser":



            if label in {"店铺运营", "平台实施"}:



                return (0, 0)



            if label == "客户运营":



                return (2, 0)



        if primary_family == "crm" and label == "客户运营":



            return (0, 0)



        if primary_family == "workflow" and label in {"平台实施", "流程设计"}:



            return (0, 0)



        return (1, 0)







    for label, supported_families, keywords in sorted(



        _ROLE_LABEL_REFINEMENT_RULES,



        key=rule_priority,



    ):



        if supported_families and not (family_set & supported_families):



            continue



        if keywords and not _role_context_matches_keywords(context_blob, keywords):



            continue



        return label



    for family_id in family_ids:



        fallback = _ROLE_LABEL_REFINEMENT_FALLBACKS.get(family_id)



        if fallback:



            return fallback



    return None











def _refine_generic_role_positioning(



    *,



    profile: IndustryProfile,



    role: IndustryRoleBlueprint,



    goal_context: list[str],



    family_ids: list[str],



) -> IndustryRoleBlueprint:



    if not _role_needs_positioning_refinement(role):



        return role



    refined_role_name = _suggest_precise_role_label(



        profile=profile,



        role=role,



        goal_context=goal_context,



        family_ids=family_ids,



    )



    if not refined_role_name:



        return role



    current_role_name = role.role_name.strip() or role.name.strip()



    if (



        _normalize_search_phrase(current_role_name).lower()



        == _normalize_search_phrase(refined_role_name).lower()



    ):



        return role



    updated_name = role.name.strip()



    if not updated_name:



        updated_name = f"{profile.primary_label()} {refined_role_name}"



    elif current_role_name and current_role_name in updated_name:



        updated_name = updated_name.replace(current_role_name, refined_role_name)



    return role.model_copy(



        update={



            "name": updated_name,



            "role_name": refined_role_name,



        },



    )











def _ordered_supported_family_ids(supported_families: frozenset[str]) -> list[str]:



    return [



        family_id



        for family_id, _label, _query, _hints in _ROLE_CAPABILITY_FAMILY_RULES



        if family_id in supported_families



    ]











def _role_scene_bundle_family_ids(role: IndustryRoleBlueprint) -> list[str]:



    label = _normalize_search_phrase(role.role_name or role.name).lower()



    if not label:



        return []



    for rule_label, supported_families, _keywords in _ROLE_LABEL_REFINEMENT_RULES:



        if label == _normalize_search_phrase(rule_label).lower():



            return _ordered_supported_family_ids(supported_families)



    return []











def _expand_role_capability_family_ids(



    *,



    role: IndustryRoleBlueprint,



    goal_context: list[str],



    family_ids: list[str],



) -> list[str]:



    normalized = _unique_strings(family_ids)



    if is_execution_core_role_id(role.role_id):



        return _unique_strings(



            ["workflow"],



            [



                family_id



                for family_id in normalized



                if family_id in _EXECUTION_CORE_ALLOWED_CAPABILITY_FAMILIES



            ],



        )[: min(_ROLE_CAPABILITY_EXPANDED_FAMILY_LIMIT, 3)]



    if role.role_id == "researcher":



        return _unique_strings(



            normalized,



            _infer_role_capability_family_ids_from_values(



                _unique_strings(



                    list(role.environment_constraints or []),



                    list(role.evidence_expectations or []),



                    goal_context[:4],



                ),



            ),



            ["research"],



        )[: min(_ROLE_CAPABILITY_EXPANDED_FAMILY_LIMIT, 3)]



    return _unique_strings(



        normalized,



        _role_scene_bundle_family_ids(role),



        _infer_role_capability_family_ids_from_values(



            _unique_strings(



                list(role.environment_constraints or []),



                list(role.evidence_expectations or []),



                goal_context[:6],



            ),



        ),



    )[:_ROLE_CAPABILITY_EXPANDED_FAMILY_LIMIT]







def _matched_capability_family_ids(



    family_ids: list[str],



    target_blob: str,



) -> list[str]:



    matched: list[str] = []



    if not target_blob:



        return matched



    for family_id in family_ids:



        rule = _capability_family_rule(family_id)



        if rule is None:



            continue



        _id, _label, query, hints = rule



        if (query and _family_needle_matches_blob(query, target_blob)) or any(



            _family_needle_matches_blob(str(needle), target_blob) for needle in hints



        ):



            matched.append(family_id)



    return _unique_strings(matched)











def _recommendation_capability_families(



    *,



    profile: IndustryProfile,



    matched_roles: list[tuple[IndustryRoleBlueprint, list[str]]],



    goal_context_by_agent: dict[str, list[str]],



    matched_family_ids: list[str] | None = None,



) -> list[str]:



    narrowed_families = _unique_strings(list(matched_family_ids or []))



    if narrowed_families:



        return narrowed_families



    families: list[str] = []



    for role, _signals in matched_roles:



        families.extend(



            _role_capability_family_ids(



                profile=profile,



                role=role,



                goal_context=goal_context_by_agent.get(role.agent_id, []),



            )



        )



    return _unique_strings(families)











def _matched_remote_guardrail_domains(blob: str) -> set[str]:



    matched: set[str] = set()



    if not blob:



        return matched



    for domain_id, terms in _REMOTE_DOMAIN_GUARDRAILS:



        if any(_family_needle_matches_blob(term, blob) for term in terms):



            matched.add(domain_id)



    return matched











def _is_generic_browser_remote_candidate(



    candidate_blob: str,



    matched_families: list[str],



) -> bool:



    normalized_families = _unique_strings(matched_families)



    non_generic_families = [



        family_id



        for family_id in normalized_families



        if family_id not in {"browser", "workflow"}



    ]



    if non_generic_families:



        return False



    return any(



        _family_needle_matches_blob(term, candidate_blob)



        for term in _GENERIC_BROWSER_REMOTE_TERMS



    )











def _execution_core_remote_candidate_allowed(



    candidate_blob: str,



    matched_families: list[str],



) -> bool:



    blocked_families = _matched_capability_family_ids(



        list(_EXECUTION_CORE_BLOCKED_CAPABILITY_FAMILIES),



        candidate_blob,



    )



    if blocked_families:



        return False



    if matched_families:



        return set(matched_families).issubset(



            set(_EXECUTION_CORE_ALLOWED_CAPABILITY_FAMILIES)



        )



    return bool(



        _matched_capability_family_ids(



            list(_EXECUTION_CORE_ALLOWED_CAPABILITY_FAMILIES),



            candidate_blob,



        )



    )











def _remote_skill_matches_guardrails(



    *,



    profile: IndustryProfile,



    role: IndustryRoleBlueprint,



    goal_context: list[str],



    candidate_blob: str,



    matched_families: list[str],



    explicit_match: str | None,



) -> bool:



    if is_execution_core_role_id(role.role_id):



        if explicit_match:



            return False



        return _execution_core_remote_candidate_allowed(candidate_blob, matched_families)



    candidate_domains = _matched_remote_guardrail_domains(candidate_blob)



    if candidate_domains:



        context_blob = _search_blob(



            _role_search_values(



                profile=profile,



                role=role,



                goal_context=goal_context,



            ),



        )



        context_domains = _matched_remote_guardrail_domains(context_blob)



        if not candidate_domains.issubset(context_domains):



            return False



    if explicit_match:



        return True



    if _is_generic_browser_remote_candidate(candidate_blob, matched_families):



        return False



    return True











def _role_specific_query_phrases(



    *,



    profile: IndustryProfile,



    role: IndustryRoleBlueprint,



    goal_context: list[str],



) -> list[str]:



    phrases: list[str] = []



    seen: set[str] = set()







    def append(value: str | None) -> None:



        normalized = _normalize_search_phrase(value)



        if not normalized:



            return



        dedupe_key = normalized.lower()



        if dedupe_key in seen:



            return



        seen.add(dedupe_key)



        phrases.append(normalized)







    role_label = _normalize_search_phrase(role.role_name or role.name)



    product_label = _normalize_search_phrase(profile.product)



    industry_label = _normalize_search_phrase(profile.industry)



    if product_label and role_label:



        append(f"{product_label} {role_label}")



    if industry_label and role_label:



        append(f"{industry_label} {role_label}")







    bucket_map = {



        bucket_id: values



        for bucket_id, values in _role_context_signal_buckets(



            profile=profile,



            role=role,



            goal_context=goal_context,



        )



    }



    for value in [



        role.role_summary,



        role.mission,



        *(bucket_map.get("history-task", [])[:2]),



        *(bucket_map.get("output-target", [])[:2]),



        *(bucket_map.get("environment-type", [])[:1]),



    ]:



        append(value)



    return phrases[:8]











def _build_hub_search_query(



    *,



    profile: IndustryProfile,



    role: IndustryRoleBlueprint,



    goal_context: list[str],



) -> str:



    candidates = _build_skillhub_query_candidates(



        profile=profile,



        role=role,



        goal_context=goal_context,



    )



    preferred = [



        candidate.query



        for candidate in candidates



        if candidate.kind in {"explicit", "role", "goal", "profile"}



    ]



    if preferred:



        return " ".join(preferred[:2])



    fallback = [candidate.query for candidate in candidates]



    return " ".join(fallback[:2])











def _build_skillhub_query_candidates(



    *,



    profile: IndustryProfile,



    role: IndustryRoleBlueprint,



    goal_context: list[str],



) -> list[_SkillHubQueryCandidate]:



    values = _role_search_values(



        profile=profile,



        role=role,



        goal_context=goal_context,



    )



    explicit_skill_names = _role_explicit_skill_names(role)



    family_ids = _expand_role_capability_family_ids(



        role=role,



        goal_context=goal_context,



        family_ids=_role_capability_family_ids(



            profile=profile,



            role=role,



            goal_context=goal_context,



        ),



    )



    candidates: list[_SkillHubQueryCandidate] = []



    seen_queries: set[str] = set()



    for skill_name in explicit_skill_names[:3]:



        _append_query_candidate(



            candidates,



            seen_queries,



            query=skill_name,



            kind="explicit",



        )



    role_phrases = _role_specific_query_phrases(



        profile=profile,



        role=role,



        goal_context=goal_context,



    )



    for phrase in role_phrases[:3]:



        _append_query_candidate(



            candidates,



            seen_queries,



            query=phrase,



            kind="role",



        )



    for family_id in family_ids[:_ROLE_CAPABILITY_EXPANDED_FAMILY_LIMIT]:



        for query in _capability_family_queries(family_id):



            _append_query_candidate(



                candidates,



                seen_queries,



                query=query,



                kind="family",



                family_id=family_id,



            )



    for phrase in role_phrases[3:]:



        _append_query_candidate(



            candidates,



            seen_queries,



            query=phrase,



            kind="goal",



        )



    english_terms = _extract_search_terms(values, limit=8)



    if english_terms:



        _append_query_candidate(



            candidates,



            seen_queries,



            query=" ".join(english_terms[:4]),



            kind="profile",



        )



    if not candidates:



        fallback_families = (



            ("workflow", "research", "content")



            if is_execution_core_role_id(role.role_id)



            else ("workflow", "research", "browser")



        )



        for family_id in fallback_families:



            _append_query_candidate(



                candidates,



                seen_queries,



                query=_capability_family_query(family_id),



                kind="family",



                family_id=family_id,



            )



    return candidates[:12]











def _fallback_query_signals(query: str) -> list[str]:



    normalized = _string(query) or ""



    if not normalized:



        return []



    return [f"标准化岗位补位：{normalized}"]











def _has_chinese_overlap(terms: list[str]) -> bool:



    """Check if any overlapping term contains Chinese characters."""



    return any(re.search(r"[\u4e00-\u9fff]", term) for term in terms)











def _build_hub_match_signals(



    *,



    profile: IndustryProfile,



    role: IndustryRoleBlueprint,



    goal_context: list[str],



    result: HubSkillResult,



) -> list[str]:



    explicit_skill_names = [



        capability.split(":", 1)[1].strip().lower()



        for capability in role.allowed_capabilities



        if capability.strip().lower().startswith("skill:")



    ]



    result_blob = _search_blob(



        [



            result.slug,



            result.name,



            result.description,



        ],



    )



    result_tokens = _tokenize_capability_hint(



        " ".join(



            _unique_strings(



                result.slug,



                result.name,



                result.description,



            ),



        ),



    )



    search_terms = _extract_search_terms(



        _role_search_values(



            profile=profile,



            role=role,



            goal_context=goal_context,



        ),



        limit=12,



    )



    overlap = [term for term in search_terms if term in result_tokens]



    signals: list[str] = []



    family_ids = _expand_role_capability_family_ids(



        role=role,



        goal_context=goal_context,



        family_ids=_role_capability_family_ids(



            profile=profile,



            role=role,



            goal_context=goal_context,



        ),



    )



    matched_families = _matched_capability_family_ids(family_ids, result_blob)



    explicit_match = next(



        (



            skill_name



            for skill_name in explicit_skill_names



            if skill_name and skill_name in result_blob



        ),



        None,



    )



    if matched_families:



        signals.append(



            "\u80fd\u529b\u65cf\u5339\u914d\uff1a" + " / ".join(_capability_family_labels(matched_families[:2]))



        )



    if explicit_match:



        signals.append(f"\u663e\u5f0f\u6280\u80fd\u7ebf\u7d22\uff1a{explicit_match}")



    # Require at least 2 token overlaps for keyword-only matches, unless



    # one of the overlapping tokens is a Chinese term (higher specificity).



    if overlap:



        has_strong_signal = bool(matched_families) or bool(explicit_match)



        has_chinese = _has_chinese_overlap(overlap)



        if has_strong_signal or has_chinese or len(overlap) >= 2:



            signals.append("\u5173\u952e\u8bcd\u5339\u914d\uff1a" + " / ".join(overlap[:3]))



    return _unique_strings(signals)











def _hub_result_key(result: HubSkillResult) -> str:



    return (



        _string(result.source_url)



        or _string(result.slug)



        or _string(result.name)



        or ""



    ).lower()











def _build_curated_match_signals(



    *,



    profile: IndustryProfile,



    role: IndustryRoleBlueprint,



    goal_context: list[str],



    item: CuratedSkillCatalogEntry,



) -> list[str]:



    explicit_skill_names = [



        capability.split(":", 1)[1].strip().lower()



        for capability in role.allowed_capabilities



        if capability.strip().lower().startswith("skill:")



    ]



    item_blob = _search_blob(



        [



            item.title,



            item.description,



            item.bundle_url,



            *list(item.tags or []),



            *list(item.capability_tags or []),



        ],



    )



    item_tokens = _tokenize_capability_hint(item_blob)



    search_terms = _extract_search_terms(



        _role_search_values(



            profile=profile,



            role=role,



            goal_context=goal_context,



        ),



        limit=12,



    )



    overlap = [term for term in search_terms if term in item_tokens]



    signals: list[str] = []



    family_ids = _expand_role_capability_family_ids(



        role=role,



        goal_context=goal_context,



        family_ids=_role_capability_family_ids(



            profile=profile,



            role=role,



            goal_context=goal_context,



        ),



    )



    matched_families = _matched_capability_family_ids(family_ids, item_blob)



    explicit_match = next(



        (



            skill_name



            for skill_name in explicit_skill_names



            if skill_name and skill_name in item_blob



        ),



        None,



    )



    if matched_families:



        signals.append(



            "\u80fd\u529b\u65cf\u5339\u914d\uff1a" + " / ".join(_capability_family_labels(matched_families[:2]))



        )



    if explicit_match:



        signals.append(f"\u663e\u5f0f\u6280\u80fd\u7ebf\u7d22\uff1a{explicit_match}")



    # Require at least 2 token overlaps for keyword-only matches, unless



    # one of the overlapping tokens is a Chinese term (higher specificity).



    if overlap:



        has_strong_signal = bool(matched_families) or bool(explicit_match)



        has_chinese = _has_chinese_overlap(overlap)



        if has_strong_signal or has_chinese or len(overlap) >= 2:



            signals.append("\u5173\u952e\u8bcd\u5339\u914d\uff1a" + " / ".join(overlap[:3]))



    return _unique_strings(signals)











def _curated_entry_key(item: CuratedSkillCatalogEntry) -> str:



    return (



        _string(item.bundle_url)



        or _string(item.candidate_id)



        or _string(item.title)



        or ""



    ).lower()











def _role_display_label(role: IndustryRoleBlueprint) -> str:



    return role.role_name.strip() or role.name.strip() or role.role_id.strip() or role.agent_id.strip()







__all__ = [name for name in globals() if not name.startswith("__")]







