#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

set -euo pipefail

find . -type f -name "*.po" -print0 | xargs -0 -I {} sh -c '
    po_file="{}"
    mo_file="${po_file%.po}.mo"
    msgfmt -o "$mo_file" "$po_file"
'