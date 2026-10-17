#!/usr/bin/env python3
"""What this service takes off a request body and remembers for it.

The marks travel in the BODY of a request and are set once, on the app, before
anything serves it. A waitress thread serves one request after another, so a
mark left standing would file the next run's figures under the last one's name.

  cd gpu_service && ../venv/bin/python -m pytest tests/test_carry_the_run.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.gpu_admission import (carry_the_run, CURRENT_RUN_LABEL,
                                    CURRENT_WORKLOAD, CURRENT_MODEL)  # noqa: E402


def _marks():
    return (CURRENT_RUN_LABEL.get(""), CURRENT_WORKLOAD.get(""),
            CURRENT_MODEL.get(""))


def test_the_marks_are_taken_off_a_body():
    carry_the_run({'run_label': 'run_1', 'workload': 'text:probe',
                   'model_id': 'a-test/probe'})
    assert _marks() == ('run_1', 'text:probe', 'a-test/probe')


def test_a_body_that_says_nothing_clears_what_stood_there():
    # A waitress thread serves one request after another. This is the whole
    # reason all three are set unconditionally.
    carry_the_run({'run_label': 'run_1'})
    carry_the_run({})
    assert _marks() == ('', '', '')


def test_a_body_that_is_not_an_object_costs_the_request_nothing():
    carry_the_run({'run_label': 'run_1'})
    for body in ([1, 2], 'a string', 7, None):
        carry_the_run(body)
        assert _marks() == ('', '', '')


if __name__ == '__main__':
    import pytest
    raise SystemExit(pytest.main([__file__, '-v']))
