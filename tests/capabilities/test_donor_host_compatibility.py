from __future__ import annotations

from copaw.capabilities.external_adapter_contracts import HostCompatibilityRequirements


def test_donor_host_compatibility_returns_compatible_native_for_matching_host() -> None:
    from copaw.capabilities.donor_host_compatibility import (
        HostCompatibilityContext,
        evaluate_donor_host_compatibility,
    )

    requirements = HostCompatibilityRequirements(
        supported_os=["windows"],
        supported_architectures=["x86_64"],
        required_runtimes=["python"],
        required_provider_contract_kind="cooperative_provider_runtime",
        required_surfaces=["network"],
        workspace_policy="workspace-write",
    )
    context = HostCompatibilityContext(
        os_name="windows",
        architecture="x86_64",
        available_runtimes=["python", "node"],
        provider_contract_kind="cooperative_provider_runtime",
        available_surfaces=["network", "shell"],
        workspace_policy="workspace-write",
    )

    result = evaluate_donor_host_compatibility(
        requirements=requirements,
        context=context,
    )

    assert result.status == "compatible_native"
    assert result.bridge_reasons == []
    assert result.blockers == []


def test_donor_host_compatibility_returns_compatible_via_bridge_for_generic_aliases() -> None:
    from copaw.capabilities.donor_host_compatibility import (
        HostCompatibilityBridgeCatalog,
        HostCompatibilityContext,
        evaluate_donor_host_compatibility,
    )

    requirements = HostCompatibilityRequirements(
        required_env_keys=["OPENAI_API_KEY"],
        config_location_expectations=["~/.config/openai/config.json"],
    )
    context = HostCompatibilityContext(
        os_name="windows",
        architecture="x86_64",
        available_runtimes=["python"],
        provider_contract_kind=None,
        available_surfaces=["network"],
        env_keys=["COPAW_PROVIDER_API_KEY"],
        config_locations=["copaw://providers/default"],
    )
    bridges = HostCompatibilityBridgeCatalog(
        env_key_aliases={"OPENAI_API_KEY": ["COPAW_PROVIDER_API_KEY"]},
        config_location_aliases={
            "~/.config/openai/config.json": ["copaw://providers/default"],
        },
    )

    result = evaluate_donor_host_compatibility(
        requirements=requirements,
        context=context,
        bridges=bridges,
    )

    assert result.status == "compatible_via_bridge"
    assert "env-alias:OPENAI_API_KEY" in result.bridge_reasons
    assert "config-alias:~/.config/openai/config.json" in result.bridge_reasons


def test_donor_host_compatibility_blocks_missing_provider_contract() -> None:
    from copaw.capabilities.donor_host_compatibility import (
        HostCompatibilityContext,
        evaluate_donor_host_compatibility,
    )

    requirements = HostCompatibilityRequirements(
        required_provider_contract_kind="cooperative_provider_runtime",
    )
    context = HostCompatibilityContext(
        os_name="windows",
        architecture="x86_64",
        available_runtimes=["python"],
        provider_contract_kind=None,
        available_surfaces=["network"],
    )

    result = evaluate_donor_host_compatibility(
        requirements=requirements,
        context=context,
    )

    assert result.status == "blocked_missing_provider_contract"
    assert "provider-contract:cooperative_provider_runtime" in result.blockers
