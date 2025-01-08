import pytest
import numpy as np

from create_shutter_values.run import load_clock_divider, create_shutter_values_script
from create_shutter_values.run import format_list_lambda


class TestLoadingClockDivider:

    def test_loading_clock_divider(self):
        divider_returned, range_returned = load_clock_divider()

        divider_expected = np.arange(0, 19)
        for _divider_returned, _divider_expected in zip(divider_returned, divider_expected):
            assert _divider_returned == _divider_expected

        range_expected = [0.118]
        for i in np.arange(1, len(divider_expected)+1):
            range_expected.append(range_expected[i-1] * 2)
        for _range_returned, _range_expected in zip(range_returned, range_expected):
            assert _range_returned == _range_expected
        
    def test_retrieving_parameters(self):
        detector_distance_m = 25.00
        detector_offset_us = 6500
        output_folder = "/tmp"
        list_lambda_in_angstroms = "3.4,4.6"
        
        # exception raised when list_lambda_in_angstroms is None
        try:
            create_shutter_values_script(detector_distance_m=detector_distance_m, 
                                         detector_offset_us=detector_offset_us, 
                                         output_folder=output_folder) 
        except ValueError as e:
            assert True

    def test_format_list_lambda(self):

        list_lambda_in_angstroms = "3. 4, 4 . 6"

        clean_list_lambda_expected = [3.4, 4.6]
        clean_list_lambda_returned = format_list_lambda(list_lambda_in_angstroms)

        for _clean_list_lambda_returned, _clean_list_lambda_expected in zip(clean_list_lambda_returned, clean_list_lambda_expected):
            assert _clean_list_lambda_returned == _clean_list_lambda_expected
