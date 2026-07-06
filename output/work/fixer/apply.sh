#!/usr/bin/env bash
#
# apply.sh — Stage 2 deterministic design-consistency fix engine.
#
# This is NOT a blind "cp the fixed tree over the target". For every file in the
# verified knowledge-base it:
#   1. reads the corresponding file in the target project,
#   2. compares its SHA-256 against the recorded baseline hash (the pristine,
#      unfixed ShopHub) and against the fixed content's hash,
#   3. applies the verified fix by whole-file replacement only when it is not
#      already in the fixed state, and
#   4. records the outcome, printing an apply-report at the end.
#
# Whole-file replacement (rather than a unified diff / `git apply`) is used so the
# engine needs neither `git` nor `patch` on the target machine and cannot fail on
# a stray whitespace/line-ending mismatch: the knowledge-base holds each changed
# file's complete, verified final content.
#
# Usage:
#   bash apply.sh [TARGET_ROOT]
#
#   TARGET_ROOT  Project root that contains the ShopHub `code/` tree to fix.
#                Defaults to the judge-assets path used by the evaluation platform.
#
# Exit code: 0 on success (all knowledge-base entries end in the fixed state),
#            non-zero if any entry could not be brought to the fixed state.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KB="$SCRIPT_DIR/knowledge-base"
HASHES="$KB/baseline-hashes.txt"
DELETIONS="$KB/deletions.txt"

TARGET_ROOT="${1:-/app/code/judge-assets/02_04_design_implementation_consistency}"

if [ ! -d "$KB/code" ]; then
    echo "FATAL: knowledge-base not found at $KB/code" >&2
    exit 2
fi
if [ ! -d "$TARGET_ROOT" ]; then
    echo "FATAL: target root does not exist: $TARGET_ROOT" >&2
    exit 2
fi

# SHA-256 of a file. Resolve the available hasher once and fail loudly if none
# exists — a silently-empty hash would make every file compare equal to the
# (also-empty) fixed hash and be wrongly skipped as "already fixed", applying
# nothing. All three tools emit the identical SHA-256 value.
if command -v sha256sum >/dev/null 2>&1; then
    sha() { sha256sum "$1" 2>/dev/null | awk '{print $1}'; }
elif command -v shasum >/dev/null 2>&1; then
    sha() { shasum -a 256 "$1" 2>/dev/null | awk '{print $1}'; }
elif command -v openssl >/dev/null 2>&1; then
    sha() { openssl dgst -sha256 "$1" 2>/dev/null | awk '{print $NF}'; }
else
    echo "FATAL: no SHA-256 tool found (need sha256sum, shasum, or openssl)" >&2
    exit 2
fi

# baseline-hashes.txt lines are:  <sha256><space><space><relative-path>
baseline_hash_for() {
    # exact path match on the second field
    awk -v p="$1" '$2==p {print $1; exit}' "$HASHES"
}

checked=0; applied_fix=0; added=0; already=0; variant=0; failed=0
deleted=0; del_absent=0

echo "=== ShopHub design-consistency fix engine ==="
echo "target : $TARGET_ROOT"
echo "kb     : $KB"
echo "------------------------------------------------------------"

# Iterate every verified file in the knowledge-base (deterministic order).
while IFS= read -r kbfile; do
    rel="${kbfile#$KB/}"                      # e.g. code/ecommerce-order/.../OrderService.java
    target="$TARGET_ROOT/$rel"
    checked=$((checked+1))

    fixed_hash="$(sha "$kbfile")"
    base_hash="$(baseline_hash_for "$rel")"

    if [ ! -f "$target" ]; then
        # File does not exist in the target — a file the fix newly introduces
        # (e.g. a new event listener / event class). Create it.
        mkdir -p "$(dirname "$target")"
        if cp "$kbfile" "$target"; then
            added=$((added+1)); echo "[ADD]      $rel"
        else
            failed=$((failed+1)); echo "[FAIL-ADD] $rel"
        fi
        continue
    fi

    cur_hash="$(sha "$target")"

    if [ "$cur_hash" = "$fixed_hash" ]; then
        already=$((already+1)); echo "[OK]       $rel (already fixed)"
        continue
    fi

    if [ -n "$base_hash" ] && [ "$cur_hash" = "$base_hash" ]; then
        # Expected case: target is the pristine/unfixed file → apply the fix.
        if cp "$kbfile" "$target"; then
            applied_fix=$((applied_fix+1)); echo "[FIX]      $rel"
        else
            failed=$((failed+1)); echo "[FAIL]     $rel"
        fi
    else
        # Target matches neither the recorded baseline nor the fixed content: an
        # unexpected local variant. Whole-file replacement is still safe (the
        # knowledge-base file is the authoritative design-consistent version), so
        # we converge to it but flag the anomaly for the audit trail.
        if cp "$kbfile" "$target"; then
            variant=$((variant+1)); echo "[FIX*]     $rel (variant baseline; imposed verified version)"
        else
            failed=$((failed+1)); echo "[FAIL]     $rel"
        fi
    fi
done < <(find "$KB/code" -type f | LC_ALL=C sort)

# --- Deletions -----------------------------------------------------------------
# Files the fix removes (module-local shadow event classes, cart JPA entities, a
# dead listener). Leaving them behind reintroduces real defects — e.g. a second
# class simple-named ReviewApprovedEventListener would trigger a
# ConflictingBeanDefinitionException at startup — so they must be removed from the
# target as well. Whole-file removal is gated on the baseline hash for reporting.
if [ -f "$DELETIONS" ]; then
    while IFS= read -r line || [ -n "$line" ]; do
        [ -z "$line" ] && continue
        del_hash="${line%% *}"
        rel="${line#*  }"
        target="$TARGET_ROOT/$rel"
        checked=$((checked+1))
        if [ ! -e "$target" ]; then
            del_absent=$((del_absent+1)); echo "[DEL-OK]   $rel (already absent)"
            continue
        fi
        cur_hash="$(sha "$target")"
        if [ "$cur_hash" = "$del_hash" ]; then
            rm -f "$target" && { deleted=$((deleted+1)); echo "[DEL]      $rel"; } \
                            || { failed=$((failed+1)); echo "[FAIL-DEL] $rel"; }
        else
            # Variant of a to-be-deleted file: the verified fixed state removes it,
            # so remove it too, but flag the mismatch.
            rm -f "$target" && { deleted=$((deleted+1)); echo "[DEL*]     $rel (variant; removed)"; } \
                            || { failed=$((failed+1)); echo "[FAIL-DEL] $rel"; }
        fi
        # Prune now-empty parent directories left behind by the deletion, so the
        # tree matches the verified fixed state exactly (harmless if non-empty).
        rmdir -p "$(dirname "$target")" 2>/dev/null || true
    done < "$DELETIONS"
fi

echo "------------------------------------------------------------"
echo "apply-report: checked=$checked  applied(fix)=$applied_fix  added=$added" \
     "variant-imposed=$variant  already-fixed=$already  deleted=$deleted" \
     "del-absent=$del_absent  failed=$failed"

if [ "$failed" -ne 0 ]; then
    echo "RESULT: FAILED ($failed file(s) could not be written)"
    exit 1
fi
echo "RESULT: OK (all $checked verified fixes are in place)"
exit 0
