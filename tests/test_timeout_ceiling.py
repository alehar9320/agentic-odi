import time

import pytest


@pytest.mark.timeout(1)
@pytest.mark.xfail(reason="demonstrates pytest-timeout halts a stalled test", strict=False)
def test_timeout_halts_a_stalled_test():
    time.sleep(3)
