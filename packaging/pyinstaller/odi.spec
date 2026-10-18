# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller onedir spec for the odi CLI.

Run from the ``cli/`` directory, e.g.::

    uv run --directory cli pyinstaller --clean --noconfirm \
        --distpath ../dist --workpath ../build/odi \
        ../packaging/pyinstaller/odi.spec
"""

import os

from PyInstaller.utils.hooks import collect_all

_spec_dir = os.path.abspath(SPECPATH)
_repo_root = os.path.dirname(os.path.dirname(_spec_dir))
_cli_src = os.path.join(_repo_root, "cli", "src")
_entry = os.path.join(_cli_src, "cli", "__main__.py")

datas = []
binaries = []
hiddenimports = []

for _pkg in (
    "fastmcp",
    "mcp",
    "pydantic",
    "pydantic_core",
    "starlette",
    "uvicorn",
    "anyio",
):
    _pkg_datas, _pkg_binaries, _pkg_hiddenimports = collect_all(_pkg)
    datas += _pkg_datas
    binaries += _pkg_binaries
    hiddenimports += _pkg_hiddenimports

hiddenimports += [
    "cli",
    "cli.cli",
    "cli.backend",
    "cli.connectors",
    "cli.context",
    "cli.outcomes",
    "cli.paths",
    "cli.update",
    "cli.version",
    "cli._build_info",
]

# Heavy optional dependencies pulled in transitively by fastmcp's optional
# extras (e.g. the ``apps``/``openai`` extras and pydantic's mypy plugin).
# The CLI never exercises these code paths and bundling them inflates the
# onedir payload by ~250 MB, so drop them.
_excludes = [
    "IPython",
    "altair",
    "matplotlib",
    "mypy",
    "narwhals",
    "numpy",
    "openai",
    "pandas",
    "PIL",
    "pyarrow",
    "pytest",
    "streamlit",
    "tkinter",
]

a = Analysis(
    [_entry],
    pathex=[_cli_src],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=_excludes,
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="odi",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="odi",
)
