"""Turning a ScanResult into something a human or a server reads."""

from verinfast2.reporting.html import render_html
from verinfast2.reporting.summary import run_summary

__all__ = ["render_html", "run_summary"]
