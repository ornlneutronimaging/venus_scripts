#!/usr/bin/env bash
#
# Wrapper to run manual_mcp_correction.py from anywhere, inside its pixi env.
#
# Usage:
#   manual_mcp_correction.sh [--using_tpx_sub_folder] [-v] <full/path/to/folder> [more folders...]
#
# Example:
#   manual_mcp_correction.sh -v /SNS/VENUS/IPTS-33699/images/mcp/my_run_set
#
set -euo pipefail

PROJECT_DIR="/gpfs/neutronsfs/instruments/VENUS/shared/software/git/venus_scripts/code"

exec pixi run --manifest-path "${PROJECT_DIR}/pixi.toml" \
    python "${PROJECT_DIR}/manual_mcp_correction.py" "$@"
