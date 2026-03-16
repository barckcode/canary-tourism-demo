"""Shared constants used across models and ETL pipelines.

Centralizes values that were previously duplicated in multiple modules
to ensure consistency and easier maintenance.
"""

# COVID exclusion range for time-series analysis.
# Used by the forecaster, scenario engine, and any module that needs
# to exclude or interpolate the pandemic disruption period.
COVID_START = "2020-03"
COVID_END = "2021-06"
