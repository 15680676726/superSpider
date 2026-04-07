# -*- coding: utf-8 -*-
from __future__ import annotations

import sqlite3

from copaw.state import SQLiteStateStore, STATE_SCHEMA_VERSION


def _column_names(conn: sqlite3.Connection, table_name: str) -> set[str]:
    return {
        str(row[1])
        for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    }


def _table_names(conn: sqlite3.Connection) -> set[str]:
    return {
        str(row[0])
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'",
        ).fetchall()
    }


def test_sqlite_state_store_initialize_upgrades_legacy_tables_before_schema_indexes(
    tmp_path,
) -> None:
    path = tmp_path / "legacy-state.sqlite3"
    with sqlite3.connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE goals (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                summary TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL,
                priority INTEGER NOT NULL DEFAULT 0,
                owner_scope TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE tasks (
                id TEXT PRIMARY KEY,
                goal_id TEXT,
                title TEXT NOT NULL,
                summary TEXT NOT NULL DEFAULT '',
                task_type TEXT NOT NULL,
                status TEXT NOT NULL,
                priority INTEGER NOT NULL DEFAULT 0,
                owner_agent_id TEXT,
                parent_task_id TEXT,
                seed_source TEXT,
                constraints_summary TEXT,
                acceptance_criteria TEXT,
                current_risk_level TEXT NOT NULL DEFAULT 'auto',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE schedules (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                cron TEXT NOT NULL,
                timezone TEXT NOT NULL,
                status TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1,
                task_type TEXT NOT NULL,
                target_channel TEXT,
                target_user_id TEXT,
                target_session_id TEXT,
                last_run_at TEXT,
                next_run_at TEXT,
                last_error TEXT,
                source_ref TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE industry_instances (
                instance_id TEXT PRIMARY KEY,
                label TEXT NOT NULL,
                summary TEXT NOT NULL DEFAULT '',
                owner_scope TEXT,
                status TEXT NOT NULL DEFAULT 'active',
                profile_payload_json TEXT NOT NULL DEFAULT '{}',
                team_payload_json TEXT NOT NULL DEFAULT '{}',
                goal_ids_json TEXT NOT NULL DEFAULT '[]',
                agent_ids_json TEXT NOT NULL DEFAULT '[]',
                schedule_ids_json TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE agent_reports (
                id TEXT PRIMARY KEY,
                industry_instance_id TEXT NOT NULL,
                cycle_id TEXT,
                assignment_id TEXT,
                goal_id TEXT,
                task_id TEXT,
                owner_agent_id TEXT,
                owner_role_id TEXT,
                report_kind TEXT NOT NULL DEFAULT 'task-terminal',
                headline TEXT NOT NULL,
                summary TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'recorded',
                result TEXT,
                risk_level TEXT NOT NULL DEFAULT 'auto',
                evidence_ids_json TEXT NOT NULL DEFAULT '[]',
                decision_ids_json TEXT NOT NULL DEFAULT '[]',
                processed INTEGER NOT NULL DEFAULT 0,
                processed_at TEXT,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )

    store = SQLiteStateStore(path)
    store.initialize()
    store.initialize()

    with sqlite3.connect(path) as conn:
        assert "buddy_domain_capabilities" in _table_names(conn)
        assert "work_contexts" in _table_names(conn)
        assert "human_assist_tasks" in _table_names(conn)
        assert "sop_adapter_templates" not in _table_names(conn)
        assert "sop_adapter_bindings" not in _table_names(conn)
        assert {
            "industry_instance_id",
            "lane_id",
            "cycle_id",
            "goal_class",
        }.issubset(_column_names(conn, "goals"))
        assert {
            "industry_instance_id",
            "assignment_id",
            "lane_id",
            "cycle_id",
            "report_back_mode",
            "work_context_id",
        }.issubset(_column_names(conn, "tasks"))
        assert {
            "spec_payload_json",
            "schedule_kind",
            "trigger_target",
            "lane_id",
        }.issubset(_column_names(conn, "schedules"))
        assert {
            "draft_payload_json",
            "execution_core_identity_payload_json",
            "lifecycle_status",
            "autonomy_status",
            "current_cycle_id",
            "next_cycle_due_at",
            "last_cycle_started_at",
        }.issubset(_column_names(conn, "industry_instances"))
        assert {"lane_id", "work_context_id"}.issubset(_column_names(conn, "agent_reports"))
        assert {
            "id",
            "title",
            "context_type",
            "status",
            "context_key",
            "primary_thread_id",
            "parent_work_context_id",
        }.issubset(_column_names(conn, "work_contexts"))
        assert {
            "domain_id",
            "profile_id",
            "domain_key",
            "domain_label",
            "status",
            "industry_instance_id",
            "control_thread_id",
            "domain_scope_summary",
            "domain_scope_tags_json",
            "capability_score",
            "capability_points",
            "settled_closure_count",
            "independent_outcome_count",
            "recent_completion_rate",
            "recent_execution_error_rate",
            "distinct_settled_cycle_count",
            "demotion_cooldown_until",
            "evolution_stage",
        }.issubset(_column_names(conn, "buddy_domain_capabilities"))
        assert {
            "chat_thread_id",
            "acceptance_mode",
            "acceptance_spec_json",
            "reward_preview_json",
            "reward_result_json",
            "submission_payload_json",
            "verification_payload_json",
        }.issubset(_column_names(conn, "human_assist_tasks"))
        assert {"work_context_id"}.issubset(_column_names(conn, "media_analyses"))
        assert conn.execute("PRAGMA user_version").fetchone()[0] == STATE_SCHEMA_VERSION
