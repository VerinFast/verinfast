#!/usr/bin/env python3
from datetime import date
import json
from pathlib import Path
import shutil
from typing import Optional
import os
from uuid import uuid4
from jinja2 import Environment, FileSystemLoader, select_autoescape
import httpx

from verinfast.utils.utils import DebugLog
from verinfast.system.sysinfo import get_system_info
from verinfast.upload import Uploader
from verinfast.config import Config
from verinfast.user import initial_prompt, save_path
from cachehash.main import Cache
from .scanner import RepositoryScanner
from .cloud import CloudScanner

today = date.today()


requestx = httpx.Client(http2=True, timeout=None)


class Agent:
    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        os.makedirs(self.config.output_dir, exist_ok=True)
        self.debug = DebugLog(file=self.config.log_file, debug=False)
        self.log = self.debug.log
        self.log(msg="", tag="Started")

        # Initialize uploader
        self.uploader = Uploader(self.config.upload_conf)
        self.up = self.uploader.make_upload_path

        self.config.upload_logs = initial_prompt()
        self.directory = save_path()

        # initialize template definition
        self.template_definition = {}
        # Set up template environment
        file_path = Path(__file__)
        parent_folder = file_path.parent.parent.absolute()
        self.templates_folder = str(parent_folder.joinpath("templates"))

        # Initialize cache
        cache_dir = Path(Path.home(), ".verinfast_cache")
        db_path = Path(cache_dir, "semgrep.db")
        if not db_path.parent.exists():
            db_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache = Cache(db_path, "semgrep_cache")

        # Initialize components
        self.scanner = RepositoryScanner(self)
        self.cloud_scanner = CloudScanner(self)

    def create_template(self):
        """Creates the HTML results template"""
        if not self.config.dry:
            try:
                output_path = f"{self.config.output_dir}/results.html"
                with open(output_path, "w") as f:
                    jinja_env = Environment(
                        loader=FileSystemLoader(self.templates_folder),
                        autoescape=select_autoescape(["html", "xml"]),
                    )
                    jinja_env.globals.update(zip=zip, sorted=sorted)
                    output = jinja_env.get_template("results.j2").render(
                        self.template_definition
                    )
                    f.write(output)
                self.log(msg=f"Template created at {output_path}", tag="Template")
            except Exception as e:
                self.log(tag="ERROR", msg=f"Template Creation Failed: {str(e)}")

    def upload(self, file: str, route: str, source: str = "", isJSON=True):
        if not self.config.shouldUpload:
            self.log(
                msg="Skipping Uploads",
                tag=f"Skipping uploading {file} for {source} to {self.config.baseUrl}/{route}.",
                display=True,
            )
            return True
        if not Path(file).exists():
            self.log(msg=f"File does not exist: {file}")
            return False

        orig_route = route

        route = self.up(
            path_type=route,
            report=self.config.reportId,
            code=self.scanId,
            repo_name=source,
        )

        with open(file, "rb") as f:
            self.log(msg=f"{self.config.baseUrl}{route}", tag="Uploading to")

            if isJSON:
                headers = {
                    "Content-Type": "application/json",
                    "accept": "application/json",
                }
                response = requestx.post(
                    self.config.baseUrl + route, data=f, headers=headers
                )
            else:
                files = {"logFile": f}
                response = requestx.post(self.config.baseUrl + route, files=files)

        if response.status_code == 200:
            self.log(
                msg="",
                tag=f"Successfully uploaded {file} for {source} to {self.config.baseUrl}{route}.",
                display=True,
            )
            try:
                err_path_str = file[0:-5] + ".err"
                err_path = Path(err_path_str)

                if err_path.exists():
                    self.upload(
                        file=err_path_str,
                        route="err_" + orig_route,
                        source=source + " Error Logs",
                        isJSON=False,
                    )
            except Exception as e:
                self.log(tag="ERROR", msg=f"Error uploading error logs: {str(e)}")

            return True
        else:
            self.log(
                msg=response.status_code,
                tag=f"Failed to upload {file} for {source} to {self.config.baseUrl}{route}",
                display=True,
            )
            return False

    def scan(self):
        """Main scan orchestration method"""
        if self.config.modules is not None:
            self.system_info = get_system_info()

            self.log(
                msg=json.dumps(self.system_info, indent=4), tag="System Information"
            )
            if not self.config.dry:
                system_info_file = os.path.join(
                    self.config.output_dir, "system_info.json"
                )
                try:
                    with open(system_info_file, "w") as f:
                        json.dump(self.system_info, f, indent=4)
                except IOError as e:
                    self.log(
                        f"Failed to write system info to {system_info_file}: {str(e)}"
                    )
                    raise RuntimeError(
                        f"Failed to write system information: {str(e)}"
                    ) from e

            if self.config.modules.code is not None or self.config.modules.cloud is not None:
                if self.config.shouldUpload:
                    headers = {
                        "content-type": "application/json",
                        "Accept-Charset": "UTF-8",
                    }
                    get_url = self.uploader.make_upload_path(
                        "scan_id", report=self.config.reportId
                    )
                    self.log(
                        msg=f"{self.config.baseUrl}{get_url}",
                        tag="Report Run Id Fetch",
                        display=True,
                    )
                    response = requestx.get(
                        f"{self.config.baseUrl}{get_url}", headers=headers
                    )
                    self.scanId = response.text.replace("'", "").replace('"', "")
                    if self.scanId and self.scanId != "":
                        self.log(msg=self.scanId, tag="Report Run Id", display=True)
                    else:
                        raise Exception(
                            f"{self.scanId} returned for failed report Id fetch."
                        )
                else:
                    self.log(
                        msg="Scan ID only fetched when uploading enabled",
                        tag="Scan ID",
                        display=True,
                    )
                self.scanner.scanRepos(self.config)

            if (
                self.config.modules
                and self.config.modules.cloud
                and len(self.config.modules.cloud)
            ):
                self.cloud_scanner.scanCloud(self.config)

            try:
                self.create_template()
            except Exception as e:
                self.log(tag="ERROR", msg=f"Template Creation Failed: {str(e)}")

        self.log(msg="", tag="Finished")


def main():
    """Main entry point for verinfast CLI"""
    agent = Agent()
    try:
        agent.scan()
    except Exception as e:
        agent.log(msg=str(e), tag="Main Scan Error Caught")
        if agent.config.upload_logs:
            agent.upload(route="logs", file=agent.config.output_dir + "/log.txt")
        raise e

    # Handle log uploads
    if agent.config.upload_logs:
        today = date.today()
        new_folder_name = str(today.year) + str(today.month) + str(today.day)
        d = agent.directory
        os.makedirs(f"{d}/{new_folder_name}/", exist_ok=True)
        new_file_name = str(uuid4()) + ".txt"
        fp = f"{d}/{new_folder_name}/{new_file_name}"
        shutil.copy2(agent.config.log_file, fp)
        print(
            f"""The log for this run was copied to:
            {d}/{new_folder_name}/{new_file_name}"""
        )

    # Handle results upload
    if agent.config.shouldUpload:
        log_list = os.listdir(agent.config.output_dir)
        log_list.sort()  # Upload current log last
        for file in log_list:
            if file.endswith("log.txt") and not file.startswith("u_"):
                file_path = os.path.join(agent.config.output_dir, file)
                agent.upload(route="logs", file=file_path, source=file, isJSON=False)
                new_path = os.path.join(agent.config.output_dir, "u_" + file)
                os.rename(file_path, new_path)

    # Show upload reminder for remote configs
    if not agent.config.shouldUpload and agent.config.is_original_path_remote():
        print("\n\n\nIMPORTANT: To upload results from this location please run")
        print(
            f"verinfast -c {agent.config.cfg_path} -o {agent.config.output_dir} --should_upload --dry"
        )


if __name__ == "__main__":
    main()
