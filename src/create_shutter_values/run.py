import os
import pandas as pd
import numpy as np
import argparse

# ===
# this is using environment
# micromamba activate /SNS/users/j35/micromamba/envs/create_shutter_values_py313
# ===


# retrieve list of hkl lambda requested by user

# user select 30 or 60Hz

# ===============

# with 30Hz, 6 ranges, with 60Hz, only 3
# starting lambda must be at least 0.3A from first hkl requested

# format of output file
# starting time, ending time, clock divider value, 10.24 (image bin, for now, we fix that value)

from create_shutter_values import clock_divider_file, default_detector_distance_m, default_detector_offset_us


def create_shutter_values_script(detector_distance_m=default_detector_distance_m, 
                                 detector_offset_us=default_detector_offset_us, 
                                 list_lambda_in_angstroms=None,
                                 output_folder="./"):
    
    if list_lambda_in_angstroms is None:
        raise ValueError("list_lambda_in_angstroms cannot be None")

    print(f"{detector_distance_m=}, {detector_offset_us=}, {list_lambda_in_angstroms=}, {output_folder=}")



def load_clock_divider():
    if not os.path.exists(clock_divider_file):
        raise FileNotFoundError(f"File {clock_divider_file} not found")
    
    pd_data = pd.read_csv(clock_divider_file, sep=",")
    divider = np.array(pd_data["Divider"])
    range = np.array(pd_data['Range (ms)'])

    return divider, range


if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='Create shutter values file for a given list of lambda',
                                     epilog='Example: python create_shutter_values.py 25.00 6500 3.4,4.6')
    parser.add_argument('--detector_distance_m', type=float, help='Distance detector_source in meters')
    parser.add_argument('--detector_offset_us', type=float, help='Detector offset in micro-seconds')
    parser.add_argument('--output_folder', type=str, help='Output folder for the shutter values file')
    parser.add_argument('list_lambda_in_angstroms', type=str, help='List of lambda in angstroms separated by comma (no space)')
    args = parser.parse_args()

    detector_distance_m = args.detector_distance_m
    detector_offset_us = args.detector_offset_us
    list_lambda_in_angstroms = args.list_lambda_in_angstroms
    output_folder = args.output_folder

    create_shutter_values_script(detector_distance_m, detector_offset_us, list_lambda_in_angstroms, output_folder)

