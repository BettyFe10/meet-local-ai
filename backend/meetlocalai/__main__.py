"""Avvio: python -m meetlocalai  [--print-port | --print-dir <chiave paths> | --check-config]"""

from __future__ import annotations

import sys

from . import config as config_mod


def main(argv: list[str]) -> int:
    try:
        cfg = config_mod.load()
    except config_mod.ConfigError as e:
        print(f"Configurazione non valida: {e}", file=sys.stderr)
        return 2
    if "--print-port" in argv:
        print(cfg["backend"]["port"])
        return 0
    if "--print-dir" in argv:
        i = argv.index("--print-dir")
        key = argv[i + 1] if i + 1 < len(argv) else ""
        dirs = config_mod.data_dirs(cfg)
        if key not in dirs:
            print(f"Chiave sconosciuta: {key}. Valide: {', '.join(dirs)}", file=sys.stderr)
            return 2
        print(dirs[key])
        return 0
    if "--check-config" in argv:
        print(f"OK: {cfg['_config_path']}")
        return 0
    import uvicorn

    from .app import create_app

    # host forzato a 127.0.0.1 (validato anche nel config)
    uvicorn.run(create_app(cfg), host="127.0.0.1", port=cfg["backend"]["port"], log_level="warning", access_log=False)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
