#!/bin/sh
# Download the trained PPO policies (GitHub release policies-v1) into runs/, where the experiment
# configs look for them as warm starts (e.g. runs/stage1-random-box-pose/model.zip).
#
#   scripts/get_policies.sh                  # into this repo's runs/
#   scripts/get_policies.sh --root /tmp/x    # into /tmp/x/runs/ instead (testing)
#   scripts/get_policies.sh --force          # replace files that differ from the release
#
# policies/manifest.json lists each release asset, where it goes and its SHA-256; every file is
# checked before it is put in place. An existing file with the same checksum is left alone; one that
# differs is kept (and reported) unless --force. Needs `gh` (logged in) and python3. Running the
# policies also needs the frozen walk/push ONNX policies: sh scripts/fetch_policies.sh
set -eu
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
ROOT="$REPO_DIR"
FORCE=0
while [ $# -gt 0 ]; do
    case "$1" in
        --root) ROOT="$2"; shift 2 ;;
        --force) FORCE=1; shift ;;
        *) echo "usage: $0 [--root DIR] [--force]" >&2; exit 2 ;;
    esac
done
MANIFEST="$REPO_DIR/policies/manifest.json"
TAG=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['release'])" "$MANIFEST")
GH_REPO=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['repo'])" "$MANIFEST")
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

echo "downloading $GH_REPO release $TAG"
gh release download "$TAG" --repo "$GH_REPO" --dir "$TMP"

python3 - "$MANIFEST" "$TMP" "$ROOT" "$FORCE" <<'EOF'
import hashlib, json, os, shutil, sys
manifest, tmp, root, force = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4] == "1"
sha = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()
bad = kept = 0
for pol in json.load(open(manifest))["policies"]:
    for f in pol["files"]:
        src, dest = os.path.join(tmp, f["asset"]), os.path.join(root, f["dest"])
        if not os.path.exists(src) or sha(src) != f["sha256"]:
            print(f"  CHECKSUM FAILED  {f['asset']}")
            bad += 1
            continue
        if os.path.exists(dest) and sha(dest) == f["sha256"]:
            print(f"  already there    {f['dest']}")
            continue
        if os.path.exists(dest) and not force:
            print(f"  kept yours       {f['dest']} (differs from the release; --force replaces it)")
            kept += 1
            continue
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.copyfile(src, dest)
        print(f"  ok               {f['dest']}  ({pol['name']})")
if bad:
    sys.exit(f"{bad} file(s) failed the checksum; nothing was written for them")
print(f"done: policies in {os.path.join(root, 'runs')}" + (f" ({kept} existing file(s) kept)" if kept else ""))
EOF
