"""Recursively copy every non-system DLL dependency of a runtime exe into a bundle dir,
then launch from there. Solves: fresh msys2 no longer ships the ffmpeg ABI-62 DLLs the
exe was linked against, and PATH-based DLL search fails inside non-MSYS launchers."""
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

MSYS_BIN = r'C:\msys64\clang64\bin'
# Extra search dirs: the ffmpeg ABI-62 DLLs were restored from the pacman cache because the
# current msys2 ships ABI 63. Checked after MSYS_BIN.
EXTRA_DIRS = [r'C:\projetos\concrete-genie-port\.cg\audit\ffmpeg-abi62']
BUNDLE = r'C:\projetos\concrete-genie-port\.cg\audit\run-bundle'
EXE = r'C:\projetos\concrete-genie-port\runtime\out\gpu\cg-runtime.exe'
# ABI-name aliases: the exe links against older sonames than current msys2 ships.
# Same ABI minor (x265 4.x, bluray 1.x); verified by the exe loading at runtime.
ALIASES = {'libx265-216.dll': 'libx265-217.dll', 'libbluray-3.dll': 'libbluray-4.dll'}

# DLLs Windows provides (apisets + system); never copy these.
SYSTEM = re.compile(
    r'^(api-ms-win-|ntdll|kernel32|kernelbase|user32|gdi32|gdi32full|shell32|shlwapi|advapi32|'
    r'sechost|rpcrt4|ole32|oleaut32|combase|bcrypt|bcryptprimitives|ncrypt|crypt32|cryptbase|'
    r'ws2_32|wsock32|winmm|imm32|version|setupapi|cfgmgr32|powrprof|pdh|msvcrt|ucrtbase|'
    r'msvcp_win|vulkan-1|dwrite|usp10|normaliz|dnsapi|iphlpapi|userenv|win32u|shcore|'
    r'dxgi|d3d11|d3d12|opengl32|glu32|msimg32|gdiplus|secur32|sspicli|sspiclr|profile|'
    r'kernel|windows\.codecs|wldp|cryptspai)', re.I)


def imports_of(pe_path):
    out = subprocess.run([os.path.join(MSYS_BIN, 'objdump.exe'), '-p', pe_path],
                         capture_output=True).stdout.decode(errors='replace')
    return [n for n in re.findall(r'DLL Name: (\S+)', out)]


def main():
    os.makedirs(BUNDLE, exist_ok=True)
    exe_in_bundle = os.path.join(BUNDLE, os.path.basename(EXE))
    shutil.copy2(EXE, exe_in_bundle)
    pending = [os.path.basename(EXE)]
    seen = set()
    missing = []
    while pending:
        name = pending.pop(0)
        if name.lower() in seen or SYSTEM.match(name):
            continue
        seen.add(name.lower())
        src = next((d / name for d in map(Path, [MSYS_BIN, *EXTRA_DIRS])
                    if (d / name).exists()), None)
        if src is None and name in ALIASES:
            src = Path(MSYS_BIN) / ALIASES[name]
        dst = os.path.join(BUNDLE, name)
        if name.lower().endswith('.exe'):
            # The executable itself: never copied from msys2 (handled above), only scanned.
            pending.extend(imports_of(exe_in_bundle))
            continue
        if src is None:
            missing.append(name)
            continue
        if not os.path.exists(dst):
            shutil.copy2(src, dst)
        pending.extend(imports_of(dst))
    if missing:
        print('MISSING (not in msys2):', missing)
        return 1
    print(f'bundle complete: {len(seen)} non-system DLLs in {BUNDLE}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
