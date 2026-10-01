"""Esegue i test JavaScript (node:test) dell'estensione."""

import shutil
import subprocess
from pathlib import Path

import pytest

HERE = Path(__file__).parent


@pytest.mark.skipif(shutil.which("node") is None, reason="node non installato")
@pytest.mark.parametrize("suite", sorted(p.name for p in HERE.glob("*.test.mjs")))
def test_node_suite(suite):
    r = subprocess.run(["node", "--test", str(HERE / suite)], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-2000:]
