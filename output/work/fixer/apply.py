#!/usr/bin/env python3
"""apply.py — Stage 2 deterministic design-consistency fix engine (python mirror).

Functionally identical to apply.sh, provided for environments where bash is
unavailable. For every file in the verified knowledge-base it reads the target,
compares SHA-256 against the recorded pristine-baseline hash and the fixed
content's hash, applies the verified fix by whole-file replacement only when
needed, removes the files listed in deletions.txt, and prints/writes an
apply-report.

Usage:  python3 apply.py [TARGET_ROOT]
        TARGET_ROOT may also come from the environment; when omitted the engine
        auto-discovers the material root (a directory containing code/pom.xml)
        by walking up from the CWD and this script's location, then scanning
        common evaluation roots.

Exit code: 0 = success, non-zero = target not found or a write failed.
Dependencies: python3 standard library only.
"""
import hashlib
import os
import shutil
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
KB = os.path.join(SCRIPT_DIR, "knowledge-base")
HASHES = os.path.join(KB, "baseline-hashes.txt")
DELETIONS = os.path.join(KB, "deletions.txt")
REPORT_PATH = os.path.join(SCRIPT_DIR, "apply-report.txt")

_report_lines = []


def out(line):
    print(line)
    _report_lines.append(line)


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def is_material_root(d):
    """The ShopHub material root contains code/pom.xml whose content really is
    the ShopHub reactor (fingerprint check — never write fixes into an unrelated
    Java project that merely has a code/ directory); never match our own KB."""
    if not d:
        return False
    pom = os.path.join(d, "code", "pom.xml")
    if not os.path.isfile(pom):
        return False
    try:
        with open(pom, encoding="utf-8", errors="replace") as f:
            content = f.read().lower()
        if "shophub" not in content and "com.ecommerce" not in content:
            return False
    except OSError:
        return False
    ad = os.path.abspath(d)
    kb = os.path.abspath(KB)
    if ad == kb or ad.startswith(kb + os.sep) or "knowledge-base" in ad.split(os.sep):
        return False
    return True


def walk_up(start):
    d = os.path.abspath(start)
    for _ in range(8):
        if is_material_root(d):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    return None


def discover_target():
    for start in (os.getcwd(), SCRIPT_DIR):
        found = walk_up(start)
        if found:
            return found
    import glob
    candidates = []
    patterns = ["/app/tasks/*/*", "/app/tasks/*", "/app/code/judge-assets/*",
                "/app/code/*", "/workspace/*", "/workspace", "/data/*",
                os.path.expanduser("~/*"), "./*"]
    for pat in patterns:
        for d in glob.glob(pat):
            if os.path.isdir(d) and is_material_root(d):
                ad = os.path.abspath(d)
                if ad not in candidates:
                    candidates.append(ad)
    if len(candidates) == 1:
        return candidates[0]
    if candidates:
        sys.stderr.write("FATAL: multiple candidate material roots found:\n")
        for c in candidates:
            sys.stderr.write("  %s\n" % c)
        sys.stderr.write("Re-run with the one in YOUR working directory: "
                         "python3 %s <that-path>\n" % sys.argv[0])
        return None
    sys.stderr.write(
        "FATAL: could not locate the ShopHub material root automatically.\n"
        "Find the directory that contains code/pom.xml (usually alongside\n"
        "design-docs/ and README.md), then re-run: python3 %s <that-path>\n"
        % sys.argv[0])
    return None


def load_two_column(path):
    """Parse '<sha256>  <relative-path>' lines into a dict path -> hash."""
    mapping = {}
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.rstrip("\n")
                if not line.strip():
                    continue
                parts = line.split(None, 1)
                if len(parts) == 2:
                    mapping[parts[1].strip()] = parts[0].strip()
    return mapping


def main(argv):
    if len(argv) >= 2 and argv[1]:
        target_root = argv[1]
        if not is_material_root(target_root):
            sys.stderr.write(
                "FATAL: '%s' does not contain code/pom.xml — not the ShopHub "
                "material root.\n" % target_root)
            return 2
    else:
        env_target = os.environ.get("TARGET_ROOT", "")
        if env_target and is_material_root(env_target):
            target_root = env_target
        else:
            target_root = discover_target()
            if not target_root:
                return 2
    target_root = os.path.abspath(target_root)

    kb_code = os.path.join(KB, "code")
    if not os.path.isdir(kb_code):
        sys.stderr.write("FATAL: knowledge-base not found at %s\n" % kb_code)
        return 2

    baseline = load_two_column(HASHES)
    deletions = load_two_column(DELETIONS)

    checked = applied = added = already = variant = failed = 0
    deleted = del_absent = 0

    out("=== ShopHub design-consistency fix engine (python) ===")
    out("target : %s" % target_root)
    out("kb     : %s" % KB)
    out("-" * 60)

    kb_files = []
    for root, _dirs, files in os.walk(kb_code):
        for name in files:
            kb_files.append(os.path.join(root, name))
    kb_files.sort()

    for kbfile in kb_files:
        rel = os.path.relpath(kbfile, KB).replace(os.sep, "/")
        target = os.path.join(target_root, rel)
        checked += 1
        fixed_hash = sha256_of(kbfile)
        base_hash = baseline.get(rel, "")

        if not os.path.isfile(target):
            try:
                os.makedirs(os.path.dirname(target), exist_ok=True)
                shutil.copyfile(kbfile, target)
                added += 1
                out("[ADD]      %s" % rel)
            except OSError as e:
                failed += 1
                out("[FAIL-ADD] %s (%s)" % (rel, e))
            continue

        cur_hash = sha256_of(target)
        if cur_hash == fixed_hash:
            already += 1
            out("[OK]       %s (already fixed)" % rel)
            continue
        try:
            shutil.copyfile(kbfile, target)
            if base_hash and cur_hash == base_hash:
                applied += 1
                out("[FIX]      %s" % rel)
            else:
                variant += 1
                out("[FIX*]     %s (variant baseline; imposed verified version)" % rel)
        except OSError as e:
            failed += 1
            out("[FAIL]     %s (%s)" % (rel, e))

    for rel, del_hash in sorted(deletions.items()):
        target = os.path.join(target_root, rel)
        checked += 1
        if not os.path.exists(target):
            del_absent += 1
            out("[DEL-OK]   %s (already absent)" % rel)
            continue
        try:
            cur_hash = sha256_of(target)
            os.remove(target)
            deleted += 1
            if cur_hash == del_hash:
                out("[DEL]      %s" % rel)
            else:
                out("[DEL*]     %s (variant; removed)" % rel)
        except OSError as e:
            failed += 1
            out("[FAIL-DEL] %s (%s)" % (rel, e))
            continue
        # prune now-empty parent directories
        d = os.path.dirname(target)
        while d and d != target_root:
            try:
                os.rmdir(d)
            except OSError:
                break
            d = os.path.dirname(d)

    out("-" * 60)
    out("apply-report: checked=%d  applied(fix)=%d  added=%d variant-imposed=%d"
        "  already-fixed=%d  deleted=%d del-absent=%d  failed=%d"
        % (checked, applied, added, variant, already, deleted, del_absent, failed))

    if failed:
        out("RESULT: FAILED (%d file(s) could not be written)" % failed)
        rc = 1
    else:
        out("RESULT: OK (all %d verified fixes are in place)" % checked)
        rc = 0

    report_text = "\n".join(_report_lines) + "\n"
    for dest in (REPORT_PATH, os.path.join(target_root, "apply-report.txt")):
        try:
            with open(dest, "w", encoding="utf-8") as f:
                f.write(report_text)
        except OSError:
            pass
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv))
