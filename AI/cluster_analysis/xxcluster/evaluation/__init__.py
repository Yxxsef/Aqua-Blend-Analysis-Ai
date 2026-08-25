"""
Evaluation harness.

    protocol.py     the shared experimental setup of Sect. 4.1
    report.py       the tables of Sect. 4.2 and Sect. 8

The distinction from `xxcluster.measures.validation` is between a
definition and its application: an index is defined once there, and applied
to every method under identical conditions here. That is what makes the
comparison of Sect. 8 a comparison -- the protocol is fixed in one place
and cannot drift between methods, because no method supplies its own.
"""

from __future__ import annotations
