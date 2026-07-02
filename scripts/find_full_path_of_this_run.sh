#!/bin/bash

if [[ -f /opt/anaconda/etc/profile.d/conda.sh ]]; then
    source /opt/anaconda/etc/profile.d/conda.sh
    conda activate ImagingReduction
fi


display_help() {
    cat <<EOF
Usage: $0 --ipts <ipts_number> --run_number <run_number>

Description:
  Retrieves the image file path (as recorded by the data acquisition
  system) for a given VENUS run.

  The script builds the path to the NeXus file:
      /SNS/VENUS/IPTS-<ipts_number>/nexus/VENUS_<run_number>.nxs.h5
  then reads and prints the value of the PV stored at:
      ["entry"]["DASlogs"]["BL10:Exp:IM:ImageFilePath"]["value"]

Options:
  --ipts <ipts_number>          IPTS number of the experiment (mandatory)
  --run_number <run_number>     Run number to look up (mandatory)
  -h, --help                    Display this help message and exit

Example:
  $0 --ipts 34808 --run_number 11133
  -> images/tpx1/raw/radiography/20250902_iPhone_Pos1_test_10_000s_0_700AngsMin/20250902_Run_11133_iPhone_Pos1_test_10_000s_0_700AngsMin_0

Exit status:
  0  PV value found and printed
  1  Missing/unknown argument, or NeXus file not found
EOF
}

# Initialize variables
ipts=""
run_number=""

# Parse arguments
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --ipts) ipts="$2"; shift ;;
        --run_number) run_number="$2"; shift ;;
        -h|--help) display_help; exit 0 ;;
        *) echo "Unknown parameter passed: $1"; exit 1 ;;
    esac
    shift
done

# Check if all required arguments are provided
if [[ -z "$ipts" || -z "$run_number" ]]; then
    echo "Usage: $0 --ipts <ipts_number> --run_number <run_number>"
    exit 1
fi

nexus_file="/SNS/VENUS/IPTS-${ipts}/nexus/VENUS_${run_number}.nxs.h5"

if [[ ! -f "$nexus_file" ]]; then
    echo "ERROR: NeXus file not found: $nexus_file" >&2
    exit 1
fi

python - "$nexus_file" <<'EOF'
import sys
import h5py
import numpy as np

nexus_file = sys.argv[1]

with h5py.File(nexus_file, "r") as nxs:
    value = nxs["entry"]["DASlogs"]["BL10:Exp:IM:ImageFilePath"]["value"][()]

for item in np.atleast_1d(value).ravel():
    print(item.decode("utf-8") if isinstance(item, bytes) else item)
EOF

# running test
# ./find_full_path_of_this_run.sh --ipts 34808 --run_number 12345
