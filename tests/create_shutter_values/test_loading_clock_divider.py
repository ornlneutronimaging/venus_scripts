import pytest
import numpy as np

from create_shutter_values.create_shutter_values import load_clock_divider


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
        