import os
import pandas as pd
import numpy as np

# ===
# this is using environment
# conda activate /SNS/users/j35/micromamba/envs/create_shutter_values_py313
# ===


# retrieve list of hkl lambda requested by user

# user select 30 or 60Hz

# ===============

# with 30Hz, 6 ranges, with 60Hz, only 3
# starting lambda must be at least 0.3A from first hkl requested

# format of output file
# starting time, ending time, clock divider value, 10.24 (image bin, for now, we fix that value)

from create_shutter_values import CLOCK_DIVIDER_FILE


def load_clock_divider():
    if not os.path.exists(CLOCK_DIVIDER_FILE):
        raise FileNotFoundError(f"File {CLOCK_DIVIDER_FILE} not found")
    
    pd_data = pd.read_csv(CLOCK_DIVIDER_FILE, sep=",")
    divider = np.array(pd_data["Divider"])
    range = np.array(pd_data['Range (ms)'])

    return divider, range
