# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""End-to-end test that ``plugin.initialize()`` layers a code-driven config over a discovered
``plugins.toml`` base, exercising the shared file-discovery + layering path through the binding."""

from __future__ import annotations

import json

from nemo_relay import ScopeType, plugin, scope


async def test_initialize_layers_code_config_over_discovered_plugins_toml(tmp_path, monkeypatch):
    # Isolate discovery to this temp project: chdir into it and point the user config dir at an
    # empty directory so only the project plugins.toml below contributes to the base.
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    project_dir = tmp_path / "project"
    (project_dir / ".nemo-relay").mkdir(parents=True)
    (project_dir / ".nemo-relay" / "plugins.toml").write_text(
        "version = 1\n\n"
        "[[components]]\n"
        'kind = "observability"\n'
        "enabled = true\n\n"
        "[components.config.atof]\n"
        "enabled = true\n"
        f'output_directory = "{out_dir}"\n'
        'filename = "from_file.jsonl"\n'
    )
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "empty-user-config"))
    monkeypatch.chdir(project_dir)

    # The code layer sets only atof.mode; output_directory/filename/enabled come from the file base.
    await plugin.initialize({"components": [{"kind": "observability", "config": {"atof": {"mode": "overwrite"}}}]})
    try:
        with scope.scope("layering-agent", ScopeType.Agent) as handle:
            scope.event("layering-mark", handle=handle, data={"step": 1})
    finally:
        plugin.clear()

    # The atof output path/name come entirely from the discovered plugins.toml (proof discovery ran),
    # and the file holds the recorded event (proof the merged config activated).
    events_file = out_dir / "from_file.jsonl"
    assert events_file.exists(), "discovered plugins.toml atof config was not applied"
    names = [json.loads(line)["name"] for line in events_file.read_text().strip().splitlines()]
    assert "layering-mark" in names
