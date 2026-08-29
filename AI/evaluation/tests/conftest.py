"""
conftest.py — makes AI/evaluation/kpi_calculator.py and kpi_gate.py
importable from this tests/ subfolder, since they live one level up.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
