#!/bin/bash
#
# find_ipts.sh - Given a VENUS run number, report the IPTS that contains it.
#
# Usage: find_ipts.sh <run_number>
#

usage() {
    echo "Usage: $(basename "$0") <run_number>"
    echo "  Looks for /SNS/VENUS/<IPTS>/nexus/VENUS_<run_number>.nxs.h5"
    exit 1
}

if [ "$#" -ne 1 ]; then
    usage
fi

run_number="$1"

# run number must be a positive integer
if ! [[ "$run_number" =~ ^[0-9]+$ ]]; then
    echo "Error: run number must be a positive integer (got '$run_number')." >&2
    usage
fi

found=0
for nexus_file in /SNS/VENUS/IPTS-*/nexus/VENUS_"${run_number}".nxs.h5; do
    # skip the literal glob if nothing matched
    [ -e "$nexus_file" ] || continue
    # extract the IPTS directory name (e.g. IPTS-12345)
    ipts=$(echo "$nexus_file" | sed -E 's#^/SNS/VENUS/(IPTS-[0-9]+)/.*#\1#')
    echo "$ipts"
    found=1
done

if [ "$found" -eq 0 ]; then
    echo "Run number $run_number not found in any IPTS." >&2
    exit 2
fi
