"""Only dump-inspected builds may enter the preparation pipeline."""

import hashlib
from pathlib import Path
import re
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "runtime" / "scripts"))
from prepare import sfo

# Documented candidates only. An empty `builds` map means: the title is recognised, but no
# build of it is supported -- every eboot is refused with its own SHA-256 in the message.
# CUSA11834 (US) is a playbook candidate and has never been seen in a dump.
# CUSA11875 (EU) was inspected locally on 2026-10-31: APP_VER 01.07,
# eboot.bin SHA-256 06f143de47f23a3ba0506e642148e2a553465bcf1e604d986ba246e5fb133e51.
# That inspection identified the build; it did NOT validate boot, imports or gameplay,
# so the build stays unregistered and no patches may run.
CANDIDATES = {
    "CUSA11834": {"name": "Concrete Genie", "region": "US", "builds": {}},
    "CUSA11875": {"name": "Concrete Genie", "region": "EU", "builds": {}},
}
# Backwards-compatible alias: earlier tooling and tests refer to PROFILES.
PROFILES = CANDIDATES


def inspect_build(game):
    game = Path(game)
    executable = game / "eboot.bin"
    if not executable.is_file():
        raise ValueError(f"No eboot.bin in {game}. Set CG_GAME_DIR or --game-dir to your dump folder.")
    try:
        metadata = sfo((game / "sce_sys" / "param.sfo").read_bytes())
    except (OSError, ValueError, IndexError, KeyError, struct.error) as error:
        raise ValueError(f"Cannot read valid sce_sys/param.sfo: {error}") from error
    title, version = metadata.get("TITLE_ID"), metadata.get("APP_VER")
    if not isinstance(title, str) or not re.fullmatch(r"CUSA[0-9]{5}", title):
        raise ValueError("Invalid or missing TITLE_ID in param.sfo")
    if not isinstance(version, str) or not re.fullmatch(r"[0-9]{2}\.[0-9]{2}", version):
        raise ValueError("Invalid or missing APP_VER in param.sfo")
    with executable.open("rb") as source:
        digest = hashlib.file_digest(source, "sha256").hexdigest()
    profile = CANDIDATES.get(title)
    if profile is None:
        raise ValueError(f"Unsupported TITLE_ID {title}; no preparation or patches applied.")
    modules = profile["builds"].get((version, digest))
    if modules is None:
        raise ValueError(f"Unvalidated build: {title} APP_VER={version} eboot SHA-256={digest}. "
                         "Candidate title only; inspect the dump before registering support. No patches applied.")
    for name in modules:
        if Path(name).name != name or not (game / "sce_module" / name).is_file():
            raise ValueError(f"Required module missing or invalid: {name}")
    return title, version, digest, modules
