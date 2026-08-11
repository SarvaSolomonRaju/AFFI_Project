#!/usr/bin/env bash
# Bundle the whole project (including the data + models + outputs that are NOT
# in git) into ONE file you can upload to a server. Run this on your laptop:
#
#     bash scripts/bundle_for_deploy.sh
#
# It writes  affi-deploy.tgz  in the project root. Upload that one file to your
# VM (see deploy/DEPLOY.md), unpack it, and run the production stack.
set -euo pipefail

cd "$(dirname "$0")/.."
OUT="affi-deploy.tgz"

echo "Bundling project -> $OUT (this includes data/, models/, outputs/) ..."

# Exclude only the things that are big/rebuildable/machine-specific. Everything
# needed to run (source, data, models, config, docker files) is included.
tar \
  --exclude='./.git' \
  --exclude='./frontend/node_modules' \
  --exclude='./frontend/dist' \
  --exclude='./venv' \
  --exclude='./.venv' \
  --exclude='./cache' \
  --exclude='*/__pycache__' \
  --exclude='*.pyc' \
  --exclude='./.pytest_cache' \
  --exclude='*/.pytest_cache' \
  --exclude='.DS_Store' \
  --exclude='./affi-deploy.tgz' \
  -czf "$OUT" .

SIZE=$(du -h "$OUT" | cut -f1)
echo
echo "Done: $OUT ($SIZE)"
echo "Next: upload it to your server, e.g."
echo "    scp $OUT ubuntu@<YOUR-SERVER-IP>:~/"
echo "Then follow deploy/DEPLOY.md on the server."
