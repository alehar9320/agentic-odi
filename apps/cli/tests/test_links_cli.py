"""Tests for the links CLI group."""

from __future__ import annotations

import json

from agentic_odi_cli.cli import app
from typer.testing import CliRunner


def _json(runner: CliRunner, args: list[str]) -> object:
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.output
    return json.loads(result.output)


def test_links_help_lists_subcommands(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()

    help_result = runner.invoke(app, ["--db", db, "links", "--help"])
    assert help_result.exit_code == 0, help_result.output
    assert "add" in help_result.output
    assert "list" in help_result.output
    assert "remove" in help_result.output


def test_links_add_creates_a_link_and_prints_id(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()

    # Create two jobs to link between
    job1 = _json(
        runner,
        [
            "--db",
            db,
            "jobs",
            "add",
            "--name",
            "Job A",
            "--json",
        ],
    )
    job1_id = str(job1["id"])

    job2 = _json(
        runner,
        [
            "--db",
            db,
            "jobs",
            "add",
            "--name",
            "Job B",
            "--json",
        ],
    )
    job2_id = str(job2["id"])

    # Add a link between them
    link = _json(
        runner,
        [
            "--db",
            db,
            "links",
            "add",
            "--source-type",
            "job",
            "--source-id",
            job1_id,
            "--target-type",
            "job",
            "--target-id",
            job2_id,
            "--relationship-type",
            "relates_to",
            "--json",
        ],
    )
    assert "id" in link
    _ = str(link["id"])
    assert link["source_type"] == "job"
    assert link["source_id"] == job1_id
    assert link["target_type"] == "job"
    assert link["target_id"] == job2_id
    assert link["relationship_type"] == "relates_to"


def test_links_list_shows_the_link(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()

    job1 = _json(runner, ["--db", db, "jobs", "add", "--name", "Job A", "--json"])
    job1_id = str(job1["id"])
    job2 = _json(runner, ["--db", db, "jobs", "add", "--name", "Job B", "--json"])
    job2_id = str(job2["id"])

    link = _json(
        runner,
        [
            "--db",
            db,
            "links",
            "add",
            "--source-type",
            "job",
            "--source-id",
            job1_id,
            "--target-type",
            "job",
            "--target-id",
            job2_id,
            "--relationship-type",
            "relates_to",
            "--json",
        ],
    )
    link_id = str(link["id"])

    # List all links
    listed = _json(runner, ["--db", db, "links", "list", "--json"])
    assert isinstance(listed, list)
    assert len(listed) == 1
    assert listed[0]["id"] == link_id
    assert listed[0]["source_type"] == "job"
    assert listed[0]["source_id"] == job1_id
    assert listed[0]["target_type"] == "job"
    assert listed[0]["target_id"] == job2_id
    assert listed[0]["relationship_type"] == "relates_to"

    # Filter by source_id
    filtered = _json(runner, ["--db", db, "links", "list", "--source-id", job1_id, "--json"])
    assert isinstance(filtered, list)
    assert len(filtered) == 1
    assert filtered[0]["id"] == link_id

    # Filter by non-matching source_id returns empty
    empty = _json(runner, ["--db", db, "links", "list", "--source-id", "non-existent", "--json"])
    assert isinstance(empty, list)
    assert len(empty) == 0

    # Filter by relationship_type
    by_rel = _json(
        runner,
        ["--db", db, "links", "list", "--relationship-type", "relates_to", "--json"],
    )
    assert isinstance(by_rel, list)
    assert len(by_rel) == 1

    # Filter by non-matching relationship_type returns empty
    empty_rel = _json(
        runner,
        ["--db", db, "links", "list", "--relationship-type", "evidence_for", "--json"],
    )
    assert isinstance(empty_rel, list)
    assert len(empty_rel) == 0


def test_links_remove_removes_the_link(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()

    job1 = _json(runner, ["--db", db, "jobs", "add", "--name", "Job A", "--json"])
    job1_id = str(job1["id"])
    job2 = _json(runner, ["--db", db, "jobs", "add", "--name", "Job B", "--json"])
    job2_id = str(job2["id"])

    link = _json(
        runner,
        [
            "--db",
            db,
            "links",
            "add",
            "--source-type",
            "job",
            "--source-id",
            job1_id,
            "--target-type",
            "job",
            "--target-id",
            job2_id,
            "--relationship-type",
            "relates_to",
            "--json",
        ],
    )
    link_id = str(link["id"])

    # Remove the link
    removed = runner.invoke(
        app,
        ["--db", db, "links", "remove", "--link-id", link_id, "--json"],
    )
    assert removed.exit_code == 0, removed.output
    removed_data = json.loads(removed.output)
    assert removed_data["id"] == link_id
    assert removed_data["deleted"] is True

    # List should now be empty
    listed = _json(runner, ["--db", db, "links", "list", "--json"])
    assert isinstance(listed, list)
    assert len(listed) == 0


def test_links_remove_unknown_id_reports_error(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()

    result = runner.invoke(app, ["--db", db, "links", "remove", "--link-id", "unknown-id"])
    assert result.exit_code != 0
    assert "No link with id" in result.output


def test_duplicate_link_add_returns_error(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()

    job1 = _json(runner, ["--db", db, "jobs", "add", "--name", "Job A", "--json"])
    job1_id = str(job1["id"])
    job2 = _json(runner, ["--db", db, "jobs", "add", "--name", "Job B", "--json"])
    job2_id = str(job2["id"])

    # Add first link
    _json(
        runner,
        [
            "--db",
            db,
            "links",
            "add",
            "--source-type",
            "job",
            "--source-id",
            job1_id,
            "--target-type",
            "job",
            "--target-id",
            job2_id,
            "--relationship-type",
            "relates_to",
            "--json",
        ],
    )

    # Add duplicate should fail
    result = runner.invoke(
        app,
        [
            "--db",
            db,
            "links",
            "add",
            "--source-type",
            "job",
            "--source-id",
            job1_id,
            "--target-type",
            "job",
            "--target-id",
            job2_id,
            "--relationship-type",
            "relates_to",
        ],
    )
    assert result.exit_code != 0
    assert "Error:" in result.output


def test_links_list_accepts_limit_and_offset(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()

    job1 = _json(runner, ["--db", db, "jobs", "add", "--name", "Job A", "--json"])
    job1_id = str(job1["id"])
    job2 = _json(runner, ["--db", db, "jobs", "add", "--name", "Job B", "--json"])
    job2_id = str(job2["id"])
    job3 = _json(runner, ["--db", db, "jobs", "add", "--name", "Job C", "--json"])
    job3_id = str(job3["id"])

    # Add three links
    _json(
        runner,
        [
            "--db",
            db,
            "links",
            "add",
            "--source-type",
            "job",
            "--source-id",
            job1_id,
            "--target-type",
            "job",
            "--target-id",
            job2_id,
            "--relationship-type",
            "relates_to",
            "--json",
        ],
    )
    _json(
        runner,
        [
            "--db",
            db,
            "links",
            "add",
            "--source-type",
            "job",
            "--source-id",
            job2_id,
            "--target-type",
            "job",
            "--target-id",
            job3_id,
            "--relationship-type",
            "blocked_by",
            "--json",
        ],
    )
    _json(
        runner,
        [
            "--db",
            db,
            "links",
            "add",
            "--source-type",
            "job",
            "--source-id",
            job1_id,
            "--target-type",
            "job",
            "--target-id",
            job3_id,
            "--relationship-type",
            "relates_to",
            "--json",
        ],
    )

    # Limit 1
    limited = _json(runner, ["--db", db, "links", "list", "--limit", "1", "--json"])
    assert isinstance(limited, list)
    assert len(limited) == 1

    # Offset 1
    offset = _json(runner, ["--db", db, "links", "list", "--offset", "1", "--json"])
    assert isinstance(offset, list)
    assert len(offset) == 2

    # Limit 1 with offset 1
    limited_offset = _json(
        runner, ["--db", db, "links", "list", "--limit", "1", "--offset", "1", "--json"]
    )
    assert isinstance(limited_offset, list)
    assert len(limited_offset) == 1
