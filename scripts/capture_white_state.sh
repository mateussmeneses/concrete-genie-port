#!/usr/bin/env bash
# Run the runtime until one execution lands in the white state, capturing frames from inside it.
#
# Why a loop: the white state appears in roughly a third of runs with identical input, so a single
# attempt usually lands in the 3D scene and proves nothing about the defect. This repeats the run,
# keeps the captures of every attempt that reached the white state, and discards the others.
#
# Each attempt writes its own log and capture directory under <out>/try<N>/, so evidence from a
# failing attempt is never overwritten by a later success.
#
# Usage:
#   scripts/capture_white_state.sh [max-attempts] [out-dir]
#
# Requires the prepared boot image (see docs/HANDOFF.md) and GOW3-style environment from
# runtime/msys2-env.sh. Everything it writes stays under .cg/, which is gitignored.
set -uo pipefail
cd -- "$(dirname -- "$0")/.."

MAX_ATTEMPTS=${1:-8}
OUT=${2:-.cg/audit/white-loop}
DUMP_DIR_ABS=$(cygpath -m "$(mkdir -p "$OUT" && cd "$OUT" && pwd)")
PAD_FILE="$DUMP_DIR_ABS/pad.txt"
APPLY_FILE="$OUT/pad_apply.txt"

RUNTIME=runtime/out/gpu/cg-runtime.exe
BOOT=.cg/audit/prepared/boot-linked.bin
CONTENT=.cg/audit/prepared/content.bin
DUMP=gamedump/CUSA11875

for path in "$RUNTIME" "$BOOT" "$CONTENT"; do
    [[ -f $path ]] || { echo "missing: $path (run the prepare/link pipeline first)" >&2; exit 1; }
done
[[ -d $DUMP ]] || { echo "missing dump directory: $DUMP" >&2; exit 1; }

source runtime/msys2-env.sh
printf 'cross\n' > "$APPLY_FILE"

for (( attempt=1; attempt<=MAX_ATTEMPTS; attempt++ )); do
    dir="$OUT/try$attempt"
    mkdir -p "$dir"
    dir_abs=$(cygpath -m "$dir")
    printf 'attempt %d/%d -> %s\n' "$attempt" "$MAX_ATTEMPTS" "$dir"

    env GOW3_FRAME_MAP=1 GOW3_FRAME_MAP_EVERY=20 \
        GOW3_FRAME_DUMP_AT=700,1500,2500 GOW3_DUMP_SYNC=1 GOW3_DUMP_DIR="$dir_abs" \
        GOW3_PAD_FILE="$PAD_FILE" \
        python scripts/state_anchored_run.py \
            --log "$dir/run.log" --pad-file "$PAD_FILE" \
            --at-state scene --settle 60 --before "$APPLY_FILE" --apply "$APPLY_FILE" \
            --timeout 380 \
            -- "$(pwd)/$RUNTIME" "$(pwd)/$BOOT" \
               --content-profile "$(pwd)/$CONTENT" \
               --app0 "$(cygpath -m "$(pwd)/$DUMP")" \
               --user "$(pwd)/.cg/audit/run/user" --timeout 350 \
        > "$dir/stdout.txt" 2>&1
    status=$?

    # Classify what this attempt actually ended in. The script must not guess: the log is the
    # record, and an attempt with no samples is a failure to observe, not a state.
    state=$(python scripts/frame_states.py "$dir/run.log" 2>/dev/null \
            | awk '/^  (black|fade|bright|scene)/ {s=$1} END {print s}')
    printf '  exit %d, final state: %s\n' "$status" "${state:-<none>}"

    if [[ $state == bright ]]; then
        echo "REACHED the white state; captures in $dir"
        python scripts/frame_workload.py "$dir/run.log" --min-frame 600 || true
        echo
        echo "Next: compare these captures - if output/display contain the scene, the port presents"
        echo "a stale buffer; if they are already white, the guest renders white."
        exit 0
    fi
done

echo "No attempt reached the white state in $MAX_ATTEMPTS runs; nothing was captured." >&2
exit 1
