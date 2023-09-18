# stdlib
import argparse
from dataclasses import dataclass
from datetime import date
from typing import List
import os
from pathlib import Path
from uuid import uuid4

# external
import httpx
import yaml

# internal
from verinfast.utils.utils import DebugLog

debugLog = DebugLog()

default_month_delta = 6

default_end_date = date.today()
default_start_year = default_end_date.year
default_start_month = default_end_date.month-default_month_delta
while default_start_month < 0:
    default_start_year -= 1
    default_start_month += 12

default_start_date = date(
    year=default_start_year,
    month=default_start_month,
    day=1  # TODO: Support arbitrary start days
)

default_start: str = (
    default_start_date.year + "-" +
    default_start_date.month + "-" +
    default_start_date.day
)
default_end: str = (
    default_end_date.year + "-" +
    default_end_date.month + "-" +
    default_end_date.day
)


@dataclass
class GitModule:
    start: str = default_start


@dataclass
class CodeModule:
    git: GitModule
    dry: bool = False
    dependencies: bool = True


@dataclass
class CloudProvider:
    """Cloud Provider

    This dataclass describes the configuration
    for a cloud provider. Currently AWS, GCP, and Azure
    are supported to various degrees

    Args:
        provider (str): A string representing a provider.
                        Today either 'aws','gcp', or 'azure'.
        account (str | int): The account identifier for the provider.
        start (str): A date in the format 'YYYY-MM-DD'
        end (str): A date in the format 'YYYY-MM-DD'

    """
    provider: str
    account: str | int
    start: str = default_start
    end: str = default_end


@dataclass
class modules:
    code: CodeModule
    cloud: List[CloudProvider]


class Config:
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
    baseUrl: str = ''
    cfg_path: str = ".verinfast.yaml"
    config = FileNotFoundError
    corsisId: int = 0
    delete_config_after = False
    # Flag to not run scans, just upload files (if shouldUpload==True)
    dry: bool = False
    output_dir = os.path.join(os.getcwd(), "results")
    reportId: int = 0
    runDependencies: bool = True
    runGit: bool = True
    runScan: bool = True
    runSizes: bool = True
    runStats: bool = True
    shouldUpload: bool = False
    shouldManualFileScan: bool = True

    def __init__(self) -> None:
        parser = self.init_argparse()
        args = parser.parse_args()
        if "config" in args and args.config is not None:
            self.cfg_path = args.config

        # TODO: Support JSON
        if self.is_path_remote():
            self.delete_config_after = True
            requestx = httpx.Client(http2=True, timeout=None)
            response = requestx.get(self.cfg_path)
            self.cfg_path = str(uuid4())+".yaml"
            with open(self.cfg_path, 'wb') as f:
                f.write(response.content)

        else:
            # If passed an argument like config.yaml does it exist here?
            # If not check the parent folder and update our internal path
            if not os.path.isfile(self.cfg_path):
                curr_path = Path(os.getcwd())
                parent = curr_path.parent
                while parent:
                    if curr_path.joinpath(self.cfg_path).exists():
                        self.cfg_path = curr_path.joinpath(self.cfg_path)
                        break
                    parent = curr_path.parent

        self.handle_config_file()
        self.handle_args(args)

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
            "-c", "--config",
            dest="config",
            help="""This argument can be used with either a local or
            remote path. A path of 'http://a.b.c/config.yaml' the
            application will download that file, save it, locally,
            parse it, and then delete it when complete.
            It will be saved with a random file name (uuid4) while
            it is on the local machine"""
        )

        parser.add_argument(
            "-o", "--output", "--output_dir",
            dest="output_dir"
        )

        parser.add_argument(
            "-d", "--dry",
            dest="dry",
            action="store_true",
            help="""This flag is boolean, and when passed will not run
            any scans. It will attempt to upload the results. It is
            primarily used for developing servers that accept these results.

            If this is passed it will set should_upload to true no matter what.
            """
        )

        parser.add_argument(
            "--should_upload",
            action="store_true",
            dest="should_upload",
            help=""" --should_upload tells the application that it should
            send the results to the bsae_url specified either as a command
            line argument or in the config.
            """
        )

        parser.add_argument(
            "--base_url",
            type=str,
            dest="base_url",
            help=""" --base_url=https://a.b.c/ will post the results of the
            scan to that url, provided the server conforms to the expected
            structure and responses."""
        )

        parser.add_argument(
            "--uuid",
            type=str,
            dest="uuid",
            help=""" --uuid specifies the secret key the receiving server
            needs to identify your upload. This can either be read from
            the config file (most common with remote configs), or passed
            here on the command line."""
        )

        return parser

    def handle_args(self, args):
        """ config.handle_args

        config.handle_args overwrites any values stored in the
        current config with the values passed on the command line.
        """
        if "output_dir" in args and args.output_dir is not None:
            self.output_dir = os.path.join(os.getcwd(), args.output_dir)

        if "uuid" in args and args.uuid is not None:
            self.reportId = args.uuid

        if "base_url" in args and args.base_url is not None:
            self.baseUrl = args.base_url

        if "should_upload" in args and args.should_upload is not None:
            self.shouldUpload = args.should_upload

        if "dry" in args and args.dry is not None:
            self.dry = args.dry

    def is_path_remote(self) -> bool:
        s = self.cfg_path

        # TODO: Add ftp
        supported_protocols = [
            "http",
            "https"
        ]

        # protocol_separator
        ps = "://"
        for sp in supported_protocols:
            if s.lower().startswith(sp+ps):
                return True
        return False

    # TODO: Support JSON
    def handle_config_file(self):
        if os.path.isfile(self.cfg_path):
            # Read the config file
            with open(self.cfg_path) as f:
                self.config = yaml.safe_load(f)

            if "modules" in self.config:
                code_modules = CodeModule()
                cloud_modules = []
                if "cloud" in self.config["modules"]:
                    c = self.config["modules"]["cloud"]
                    for row in c:
                        provider = CloudProvider(
                            provider=row["provider"],
                            account=row["account"],
                            start=row["start"],
                            end=row["end"]
                        )
                        cloud_modules.append(provider)
                self.modules = modules(code=code_modules, cloud=cloud_modules)

            debugLog.log(msg=self.config, tag="Config", display=True)
