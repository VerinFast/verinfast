import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from verinfast.utils.utils import DebugLog

from .constants import DEFAULT_CONFIG_PATH, DEFAULT_SCAN_PATH
from .modules import ConfigModules, CodeModule, GitModule
from .modules.upload import UploadConfig
from .parsers.args import init_argparse, handle_args
from .parsers.file import (
    is_remote_path, fetch_remote_config,
    find_config_file, parse_config_file
)
from .utils.printable import Printable


class Config(Printable):
    """VerinFast Configuration

    Handles configuration from .verinfast.yaml file and command line arguments.
    Searches for config file in current and parent directories.
    """

    # TODO: Add support for JSON configuration files.
    # Currently only supports YAML format.

    def __init__(self, cfg_path: Optional[str] = None) -> None:
        # Initialize basic attributes
        self.baseUrl: str = ''
        self.cfg_path: str = cfg_path or DEFAULT_CONFIG_PATH
        self.original_cfg_path: str = self.cfg_path
        self.config = FileNotFoundError
        self.reportId: int = 0
        self.scanId: int = 0
        self.delete_config_after = False
        self.delete_temp = True
        self.dry: bool = False
        self.local_scan_path: str = DEFAULT_SCAN_PATH
        self.modules = ConfigModules(
                    code=CodeModule(git=GitModule()),
                    cloud=[]
                )

        # Set up paths
        self.output_dir = os.path.join(os.getcwd(), "results")
        self.log_file = os.path.join(
            self.output_dir,
            datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + "_log.txt"
        )

        # Initialize flags
        self.reportId: int = 0
        self.runDependencies: bool = True
        self.runGit: bool = True
        self.runScan: bool = True
        self.runSizes: bool = True
        self.runStats: bool = True

        # Server configuration
        self.server_prefix: Optional[str] = None
        self.server_code_separator: Optional[str] = None
        self.server_cost_separator: Optional[str] = None

        # Upload configuration
        self.shouldUpload: bool = False
        self.shouldManualFileScan: bool = True
        self.truncate_findings = False
        self.truncate_findings_length = 30
        self.upload_logs = False
        self.use_uuid = False

        # Handle configuration
        self._initialize_configuration()

    def init_argparse(self):
        # delegate to the argument parser
        return init_argparse()

    def handle_args(self, args):
        """Delegate to the argument handler"""
        handle_args(self, args)

    def is_original_path_remote(self) -> bool:
        """Check if config path is remote"""
        s = self.original_cfg_path
        # TODO: Add ftp
        supported_protocols = ["http", "https"]
        ps = "://"
        for sp in supported_protocols:
            if s.lower().startswith(sp+ps):
                return True
        return False

    def _initialize_configuration(self) -> None:
        """Initialize configuration from file and arguments"""
        # Parse command line arguments if not in test mode
        args = None
        if 'pytest' not in sys.argv[0]:
            parser = init_argparse()
            args = parser.parse_args()
            if args.config:
                self.cfg_path = args.config
                self.original_cfg_path = args.config

        # Handle remote configuration
        if is_remote_path(self.original_cfg_path):
            self.delete_config_after = True
            self.cfg_path = fetch_remote_config(self.cfg_path)
        else:
            self.cfg_path = str(find_config_file(self.cfg_path))

        # Parse configuration file
        self.config = parse_config_file(self, self.cfg_path)

        # Handle empty or missing config
        if self.config is FileNotFoundError:
            self.config = {}

        # Set default local repository if no targets specified
        if (
            "repos" not in self.config and
            "local_repos" not in self.config and
            (
                "modules" not in self.config or
                "cloud" not in self.config["modules"]
            )
        ):
            self.config["local_repos"] = [self.local_scan_path]
            gm = GitModule()
            cm = CodeModule(git=gm)
            self.modules = ConfigModules(code=cm, cloud=[])
            self.runGit = False

        # Apply command line arguments
        if args and 'pytest' not in sys.argv[0]:
            handle_args(self, args)
        # Set up logging
        self._initialize_logging(args)

        # Set default configuration if needed
        self._set_default_config()

        # Initialize upload configuration
        self._initialize_upload_config()

    def handle_config_file(self) -> None:
        """Parse and apply configuration from file"""
        self.config = parse_config_file(self, self.cfg_path)

    def _set_default_config(self) -> None:
        """Set default configuration if none provided"""
        if self.config is FileNotFoundError:
            self.config = {}

        # Set default local repository if no targets specified
        if (
            "repos" not in self.config and
            "local_repos" not in self.config and
            (
                "modules" not in self.config or
                "cloud" not in self.config["modules"]
            )
        ):
            self.config["local_repos"] = [self.local_scan_path]
            gm = GitModule()
            cm = CodeModule(git=gm)
            self.modules = ConfigModules(code=cm, cloud=[])
            self.runGit = False
        elif (
            "repos" in self.config and
            "modules" in self.config and
            "code" in self.config["modules"] and
            "git" in self.config["modules"]["code"]
        ):
            self.runGit = True

    def _initialize_upload_config(self) -> None:
        """Initialize upload configuration"""

        self.upload_conf = UploadConfig(uuid=self.use_uuid)

        if self.server_cost_separator is not None:
            self.upload_conf.cost_separator = self.server_cost_separator
        if self.server_prefix is not None:
            self.upload_conf.prefix = self.server_prefix
        if self.server_code_separator is not None:
            self.upload_conf.code_separator = self.server_code_separator

    def _initialize_logging(self, args) -> None:
        """Initialize logging configuration"""
        os.makedirs(self.output_dir, exist_ok=True)
        self.log_file = os.path.join(
            self.output_dir,
            datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + "_log.txt"
        )

        debugLog = DebugLog(file=self.log_file)
        debugLog.log(msg="VerinFast Scan Started", tag="", display=True)
        debugLog.log(msg=self.config, tag="Loaded Configuration", display=True)

        if 'pytest' not in sys.argv[0]:
            debugLog.log(msg=args, tag="Arguments", display=True)

        debugLog.log(msg={
            "baseurl": self.baseUrl,
            "should_upload": self.shouldUpload,
            "dry": self.dry,
            "uuid": self.reportId,
        }, tag="Run Configuration", display=True)
