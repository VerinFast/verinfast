import argparse
import os
from typing import Any


def init_argparse() -> argparse.ArgumentParser:
    """Initialize argument parser

    Note: Defaults are intentionally omitted to prevent
    overwriting config file values
    """
    parser = argparse.ArgumentParser(
        prog="verinfast",
        usage="%(prog)s [OPTION] [FILE]..."
    )

    parser.add_argument(
        "-c", "--config",
        dest="config",
        help="Path to config file (local or remote)"
    )

    parser.add_argument(
        "-o", "--output", "--output_dir",
        dest="output_dir",
        help="Output directory for results"
    )

    parser.add_argument(
        "-t", "--truncate", "--truncate_findings",
        dest="truncate_findings",
        type=int,
        help="""This flag will further enhance privacy by capping
                The length of security warnings. It defaults to unlimited,
                but can be set to any level you feel comfortable with.

                <0 = unlimited
                We recommend 30 as good balance between privacy and utility
                """
        )

    parser.add_argument(
        "-d", "--dry",
        dest="dry",
        action="store_true",
        help="Skip scans, only attempt uploads"
    )

    parser.add_argument(
        "--should_upload",
        action="store_true",
        dest="should_upload",
        help="Enable result upload to specified base_url"
    )

    parser.add_argument(
        "--base_url",
        type=str,
        dest="base_url",
        help="Server URL for uploading results"
    )

    parser.add_argument(
        "--uuid",
        type=str,
        dest="uuid",
        help="Secret key for server identification"
    )

    parser.add_argument(
        "--path",
        type=str,
        dest="local_scan_path",
        help="Single path to scan (ignored if config specifies repos)"
    )

    parser.add_argument(
        "--should_git", "-g",
        action="store_true",
        dest="should_git",
        help="""Used to skip contributions and only run a
                    code quality scan."""
    )

    return parser


def handle_args(config: Any, args: argparse.Namespace) -> None:
    """Update config with command line arguments

    Args:
        config: Config instance to update
        args: Parsed command line arguments
    """
    if args.output_dir:
        config.output_dir = os.path.join(os.getcwd(), args.output_dir)

    if args.uuid:
        config.reportId = args.uuid
        config.use_uuid = True

    if args.base_url:
        config.baseUrl = args.base_url

    if args.should_upload:
        config.shouldUpload = True

    if args.dry:
        config.dry = True
        config.shouldUpload = True

    if args.local_scan_path:
        config.local_scan_path = args.local_scan_path

    if args.should_git:
        config.runGit = args.should_git

    if args.truncate_findings is not None:
        if args.truncate_findings >= 0:
            config.truncate_findings = True
            config.truncate_findings_length = args.truncate_findings
        else:
            config.truncate_findings = False
