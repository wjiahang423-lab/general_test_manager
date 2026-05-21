"""
Central path configuration for the general test manager.
All paths are resolved relative to the project root.
"""

from __future__ import annotations
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))

REPORTS_DIR      = os.path.join(PROJECT_ROOT, "reports")
TEST_PLANS_DIR   = os.path.join(PROJECT_ROOT, "test_plans")
TEST_SCRIPTS_DIR = os.path.join(PROJECT_ROOT, "test_scripts")

for _d in (REPORTS_DIR, TEST_PLANS_DIR, TEST_SCRIPTS_DIR):
    os.makedirs(_d, exist_ok=True)
