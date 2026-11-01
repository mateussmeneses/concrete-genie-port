#!/usr/bin/env bash
# Reproducible Windows build for the Concrete Genie port (MSYS2 CLANG64).
# Every step fails loudly: no --reject, no swallowed exit codes.
set -euo pipefail
cd -- "$(dirname -- "$0")"
case "${1:-}" in ""|--test) ;; *) echo 'Usage: bash build.sh [--test]' >&2; exit 2;; esac
case $(uname -s) in MINGW*|MSYS*) ;; *) echo 'Use MSYS2 CLANG64 on Windows.' >&2; exit 1;; esac
MSYS2_ROOT=${CG_MSYS2_ROOT:-${MSYS2_ROOT:-/c/msys64}}
source runtime/msys2-env.sh
for tool in git clang cmake ninja pkg-config python; do
    command -v "$tool" >/dev/null || { echo "Missing CLANG64 dependency: $tool (see docs/BASELINE.md)" >&2; exit 1; }
done
# Native Windows tools cannot open MSYS-style /c/... paths: translate the project root once and
# pass that form to git. Without this the patch step silently reported "already applied" on a
# checkout where the patch had never been applied.
PROJECT_ROOT=$(cygpath -m "$PWD")

echo '== Submodules =='
git submodule update --init --recursive
if git submodule status --recursive | grep -qE '^-'; then
    echo 'Submodule initialization failed; run: git submodule update --init --recursive' >&2
    exit 1
fi

echo '== Third-party patches (idempotent) =='
shopt -s nullglob
fsr_patches=(runtime/gpu/patches/fsr-vulkan/*.patch)
shopt -u nullglob
if (( ${#fsr_patches[@]} == 0 )); then
    echo 'No FSR-Vulkan patches found; expected runtime/gpu/patches/fsr-vulkan/*.patch' >&2
    exit 1
fi
for patch in "${fsr_patches[@]}"; do
    absolute="$PROJECT_ROOT/${patch#./}"
    if git -C runtime/gpu/third_party/fsr-vulkan apply --reverse --check "$absolute" 2>/dev/null; then
        echo "Already applied: $patch"
        continue
    fi
    # Forward check first: a patch matching neither direction must stop the build, never be skipped.
    if ! git -C runtime/gpu/third_party/fsr-vulkan apply --check "$absolute"; then
        echo "Patch applies neither forward nor in reverse: $patch" >&2
        echo 'The submodule checkout differs from its pinned revision; inspect it instead of forcing.' >&2
        exit 1
    fi
    git -C runtime/gpu/third_party/fsr-vulkan apply "$absolute"
    echo "Applied: $patch"
done

export CXXFLAGS="${CXXFLAGS:-} -include cstdlib -include cstdio -include cwchar -include cmath -include new"
# Native Windows tools spawned by the build (windres for the .rc resources, clang's linker) cannot
# create files in an MSYS-style /tmp. Keep their temp files in a real Windows directory under out/.
TEMP_DIR="$PROJECT_ROOT/runtime/out/tmp"
mkdir -p "$TEMP_DIR"
export TMP="$TEMP_DIR" TEMP="$TEMP_DIR" TMPDIR="$TEMP_DIR"
echo '== Configure =='
cmake -S runtime/gpu -B runtime/out/gpu -G Ninja -DCMAKE_BUILD_TYPE=RelWithDebInfo \
    -DGOW3_PGO=off -DGOW3_LTO=OFF -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++
echo '== Build =='
ninja -C runtime/out/gpu cg-runtime cg-gpu-check
if [[ ${1:-} == --test ]]; then
    echo '== Native tests =='
    tests=(services-test pad-map-test aliasing-test depth-stencil-state-test async-compiler-test warmup-inbox-test)
    ninja -C runtime/out/gpu "${tests[@]}"
    for test in "${tests[@]}"; do
        echo "RUN $test"
        "runtime/out/gpu/$test.exe"
    done
fi
echo "Built $PROJECT_ROOT/runtime/out/gpu/cg-runtime.exe"
