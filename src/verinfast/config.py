# stdlib
import argparse
from dataclasses import dataclass, field, is_dataclass, asdict
from datetime import date, datetime
import json
from typing import List, Optional
import os
from pathlib import Path
import sys
from uuid import uuid4
from typing import Union

# external
import httpx
import yaml

# internal
from verinfast.utils.utils import DebugLog

default_month_delta = 6

default_end_date = date.today()
default_start_year = default_end_date.year
default_start_month = default_end_date.month - default_month_delta
while default_start_month <= 0:
    default_start_year -= 1
    default_start_month += 12

default_start_date = date(
    year=default_start_year,
    month=default_start_month,
    day=1,  # TODO: Support arbitrary start days
)

default_start: str = (
    f"{default_start_date.year}-{default_start_date.month}-{default_start_date.day}"
)
default_end: str = (
    f"{default_end_date.year}-{default_end_date.month}-{default_end_date.day}"
)


class printable:
    def __str__(self):
        d = {}
        for key in dir(self):
            x = self.__getattribute__(key)
            if not key.startswith("_") and not callable(x):
                if is_dataclass(x):
                    d[key] = asdict(x)
                elif isinstance(x, date):
                    d[key] = x.strftime("%Y-%mm-%dd")
                elif x is None:
                    d[key] = None
                else:
                    d[key] = x.__str__()

        return json.dumps(d, indent=4, default=str)

    # Dictionary-like access / updates
    # def __getitem__(self, name):
    #     value = self.__dict[name]
    #     if isinstance(value, dict):  # recursively view sub-dicts as objects
    #         value = printable(value)
    #     return value

    # def __setitem__(self, name, value):
    #     self.__dict[name] = value

    # def __delitem__(self, name):
    #     del self.__dict[name]

    # # Object-like access / updates
    # def __getattr__(self, name):
    #     return self[name]

    # def __setattr__(self, name, value):
    #     self[name] = value

    # def __delattr__(self, name):
    #     del self[name]


@dataclass
class UploadConfig(printable):
    """
    Args:
        uuid (bool) : specifies whether to use the uuid path prefix
        prefix (str) : defaults to "/report" if not specified
    """

    uuid: bool = False
    prefix: Union[str, None] = "/report/"
    code_separator: Union[str, None] = "/CorsisCode"
    cost_separator: Union[str, None] = None


@dataclass
class GitModule(printable):
    start: str = default_start


@dataclass
class CodeModule(printable):
    git: GitModule
    dry: bool = False
    dependencies: bool = True


@dataclass
class CloudProvider(printable):
    """Cloud Provider

    This dataclass describes the configuration
    for a cloud provider. Currently AWS, GCP, and Azure
    are supported to various degrees

    Args:
        provider (str): A string representing a provider.
                        Today either 'aws','gcp', or 'azure'.
        account (Union[str, int]): The account identifier for the provider.
        profile (str): Profile credentials to use.
        start (str): A date in the format 'YYYY-MM-DD'
        end (str): A date in the format 'YYYY-MM-DD'

    """

    provider: str
    account: Union[str, int]
    profile: Optional[str] = None
    start: str = default_start
    end: str = default_end


@dataclass
class ConfigModules(printable):
    code: CodeModule = None
    cloud: List[CloudProvider] = field(default_factory=list)


class Config(printable):
    """VerinFast Config
    VerinFast takes configuration from either a .verinfast.yaml file
    or from the command line via arguments. The program will look for
    a .verinfast.yaml file in the current directory or any ancestor,
    stopping when it finds the first.

    Some values are set in the class definition, and are not generally
    overwriteable. That may change in the future, but for now these
    are intentionally not exposed and are consider for developer use
    only. Examples include: "runGit", "runSizes", etc. Modifying these
    could have unanticipated side effects.
    """

    baseUrl: str = ""
    cfg_path: str = ".verinfast.yaml"
    original_cfg_path: str = ".verinfast.yaml"
    config = FileNotFoundError
    scanId: int = 0
    delete_config_after = False
    delete_temp = True
    # Flag to not run scans, just upload files (if shouldUpload==True)
    dry: bool = False
    local_scan_path: str = "./"
    modules: Union[ConfigModules, None] = None
    output_dir = os.path.join(os.getcwd(), "results")
    log_file = os.path.join(
        output_dir, datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + "_log.txt"
    )
    reportId: int = 0
    runDependencies: bool = True
    runGit: bool = True
    runScan: bool = True
    runSizes: bool = True
    runStats: bool = True
    server_prefix: Union[str, None] = None
    server_code_separator: Union[str, None] = None
    server_cost_separator: Union[str, None] = None
    shouldUpload: bool = False
    shouldManualFileScan: bool = True
    truncate_findings = False
    truncate_findings_length = 30
    upload_logs = False
    use_uuid = False

    def __init__(self, cfg_path: str = None) -> None:
        if cfg_path is not None:
            self.cfg_path = cfg_path
            self.original_cfg_path = cfg_path
        elif "pytest" not in sys.argv[0]:
            parser = self.init_argparse()
            args = parser.parse_args()
            if "config" in args and args.config is not None:
                self.cfg_path = args.config
                self.original_cfg_path = args.config

        # TODO: Support JSON
        if self.is_original_path_remote():
            self.delete_config_after = True
            requestx = httpx.Client(http2=True, timeout=None)
            response = requestx.get(self.cfg_path)
            self.cfg_path = str(uuid4()) + ".yaml"
            with open(self.cfg_path, "wb") as f:
                f.write(response.content)

        else:
            # If passed an argument like config.yaml does it exist here?
            # If not check the parent folder and update our internal path
            if not os.path.isfile(self.cfg_path):
                curr_path = Path(os.getcwd())
                parent = curr_path.parent
                while parent and Path(curr_path) != Path("/"):
                    if curr_path.joinpath(self.cfg_path).exists():
                        self.cfg_path = curr_path.joinpath(self.cfg_path)
                        break
                    parent = curr_path.parent
                    curr_path = parent
        self.handle_config_file()
        if "pytest" not in sys.argv[0]:
            self.handle_args(args)
        if self.config is FileNotFoundError:
            self.config = {}
        """
        If run with no arguments assume we want to scan the current directory.
        If a scan target is not set by the command line or config we set the
        target to be ["./"]
        """
        if (
            "repos" not in self.config
            and "local_repos" not in self.config
            and ("modules" not in self.config or "cloud" not in self.config["modules"])
        ):
            self.config["local_repos"] = [self.local_scan_path]
            gm = GitModule()
            cm = CodeModule(git=gm)
            """
                The line below previously overwrote existing modules.
            """
            self.modules = ConfigModules(code=cm, cloud=[])
            self.runGit = False
        elif (
            "repos" in self.config
            and "modules" in self.config
            and "code" in self.config["modules"]
            and "git" in self.config["modules"]["code"]
        ):
            self.runGit = True
        self.upload_conf = UploadConfig(uuid=self.use_uuid)
        if self.server_cost_separator is not None:
            self.upload_conf.cost_separator = self.server_cost_separator
        if self.server_prefix is not None:
            self.upload_conf.prefix = self.server_prefix
        if self.server_code_separator is not None:
            self.upload_conf.code_separator = self.server_code_separator

        os.makedirs(self.output_dir, exist_ok=True)
        self.log_file = os.path.join(
            self.output_dir, datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + "_log.txt"
        )
        debugLog = DebugLog(file=self.log_file)
        debugLog.log(msg="VerinFast Scan Started", tag="", display=True)
        debugLog.log(msg=self.config, tag="Loaded Configuration", display=True)
        if "pytest" not in sys.argv[0]:
            debugLog.log(msg=args, tag="Arguments", display=True)
        debugLog.log(
            msg={
                "baseurl": self.baseUrl,
                "should_upload": self.shouldUpload,
                "dry": self.dry,
                "uuid": self.reportId,
            },
            tag="Run Configuration",
            display=True,
        )

    def init_argparse(self) -> argparse.ArgumentParser:
        """config.init_argparse

        Note: Never use default values here. If a value is in the
        arg list it will overwrite the existing value. When a
        default value is used, it always shows up in the arg list
        which means it will overwrite a value already specified in
        a config file, which is not the desired behavior.
        """
        parser = argparse.ArgumentParser(
            prog="verinfast",
            usage="%(prog)s [OPTION] [FILE]...",
            # TODO: Description
            # description="Print or check SHA1 (160-bit) checksums."
        )

        parser.add_argument(
            "-c",
            "--config",
            dest="config",
            help="""This argument can be used with either a local or
            remote path. A path of 'http://a.b.c/config.yaml' the
            application will download that file, save it, locally,
            parse it, and then delete it when complete.
            It will be saved with a random file name (uuid4) while
            it is on the local machine""",
        )

        parser.add_argument("-o", "--output", "--output_dir", dest="output_dir")

        parser.add_argument(
            "-t",
            "--truncate",
            "--truncate_findings",
            dest="truncate_findings",
            type=int,
            help="""This flag will further enhance privacy by capping
            The length of security warnings. It defaults to unlimited,
            but can be set to any level you feel comfortable with.

            <0 = unlimited
            We recommend 30 as good balance between privacy and utility
            """,
        )

        parser.add_argument(
            "-d",
            "--dry",
            dest="dry",
            action="store_true",
            help="""This flag is boolean, and when passed will not run
            any scans. It will attempt to upload the results. It is
            primarily used for developing servers that accept these results.

            If this is passed it will set should_upload to true no matter what.
            """,
        )

        parser.add_argument(
            "--should_upload",
            action="store_true",
            dest="should_upload",
            help=""" --should_upload tells the application that it should
            send the results to the bsae_url specified either as a command
            line argument or in the config.
            """,
        )

        parser.add_argument(
            "--base_url",
            type=str,
            dest="base_url",
            help=""" --base_url=https://a.b.c/ will post the results of the
            scan to that url, provided the server conforms to the expected
            structure and responses.""",
        )

        parser.add_argument(
            "--uuid",
            type=str,
            dest="uuid",
            help=""" --uuid specifies the secret key the receiving server
            needs to identify your upload. This can either be read from
            the config file (most common with remote configs), or passed
            here on the command line.""",
        )

        parser.add_argument(
            "--path",
            type=str,
            dest="local_scan_path",
            help="""This argument will be ignored if a config file specifies
            repositories to scan. This is only used for a single path scan.
            """,
        )

        parser.add_argument(
            "--should_git",
            "-g",
            action="store_true",
            dest="should_git",
            help="""Used to skip contributions and only run a
            code quality scan.""",
        )

        return parser

    def handle_args(self, args):
        """config.handle_args

        config.handle_args overwrites any values stored in the
        current config with the values passed on the command line.
        """

        if "output_dir" in args and args.output_dir is not None:
            self.output_dir = os.path.join(os.getcwd(), args.output_dir)

        if "uuid" in args and args.uuid is not None:
            self.reportId = args.uuid
            self.use_uuid = True

        if "base_url" in args and args.base_url is not None:
            self.baseUrl = args.base_url

        if "should_upload" in args and args.should_upload:
            self.shouldUpload = True

        if "dry" in args and args.dry:
            self.dry = True

        if "local_scan_path" in args and args.local_scan_path is not None:
            self.local_scan_path = args.local_scan_path

        if "should_git" in args and args.should_git is True:
            self.runGit = args.should_git

        if "truncate_findings" in args and args.truncate_findings is not None:
            if args.truncate_findings >= 0:
                self.truncate_findings = True
                self.truncate_findings_length = args.truncate_findings
            else:
                self.truncate_findings = False

    def is_original_path_remote(self) -> bool:
        s = self.original_cfg_path

        # TODO: Add ftp
        supported_protocols = ["http", "https"]

        # protocol_separator
        ps = "://"
        for sp in supported_protocols:
            if s.lower().startswith(sp + ps):
                return True
        return False

    # TODO: Support JSON
    def handle_config_file(self):
        if os.path.isfile(self.cfg_path):
            # Read the config file
            with open(self.cfg_path) as f:
                self.config = yaml.safe_load(f)

            # Global Configuration
            if "baseurl" in self.config:
                self.baseUrl = self.config["baseurl"]
            if "should_upload" in self.config:
                self.shouldUpload = self.config["should_upload"]
            if "dry" in self.config:
                self.dry = self.config["dry"]
            if "delete_temp" in self.config:
                self.delete_temp = self.config["delete_temp"]
            if "truncate_findings" in self.config:
                self.truncate_findings = self.config["truncate_findings"]
                if "truncate_findings_length" in self.config:
                    self.truncate_findings_length = self.config[
                        "truncate_findings_length"
                    ]
                else:
                    self.truncate_findings_length = 30

            if "server" in self.config:
                s = self.config["server"]
                if "prefix" in s:
                    self.server_prefix = s["prefix"]
                if "code_separator" in s:
                    self.server_code_separator = s["code_separator"]
                if "cost_separator" in s:
                    self.server_cost_separator = s["cost_separator"]

            if "report" in self.config:
                if "uuid" in self.config["report"]:
                    self.use_uuid = True
                    self.reportId = self.config["report"]["uuid"]
                elif "id" in self.config["report"]:
                    self.reportId = self.config["report"]["id"]

            # Module specific configuration
            if "modules" in self.config:
                m = self.config["modules"]
                gm = GitModule()
                code_modules = CodeModule(git=gm)
                if "code" in m:
                    c = m["code"]
                    if "run_git" in c:
                        self.runGit = c["run_git"]
                    if "run_scan" in c:
                        self.runScan = c["run_scan"]
                    if "run_sizes" in c:
                        self.runSizes = c["run_sizes"]
                    if "run_stats" in c:
                        self.runStats = c["run_stats"]
                    if "git" in c:
                        g = ["git"]
                        if "start" in g:
                            gm.start = g["start"]
                    if "dependencies" in c:
                        self.runDependencies = c["dependencies"]
                cloud_modules = []
                if "cloud" in m:
                    c = m["cloud"]
                    for row in c:
                        provider = CloudProvider(**row)
                        cloud_modules.append(provider)
                self.modules = ConfigModules(code=code_modules, cloud=cloud_modules)
