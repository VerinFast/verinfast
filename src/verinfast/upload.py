from verinfast.config import UploadConfig
from typing import Union


class Uploader:
    def __init__(self, config: UploadConfig):
        self.config = config

    def make_upload_path(
        self,
        path_type: str,
        report: Union[str, int],
        code: Union[str, int] = None,
        repo_name: str = None,
    ) -> str:
        """make_upload_path
        make_upload_path is a convenience function for abstracting
        the url paths from the scanning logic.

        Args:
            path_type (str) : specifies the scan action triggering the upload
            report (Union[str, int]): specifies the identifier the server uses for this scan
            code (Union[str, int]) :
        """

        code_sep = self.config.code_separator or ""

        cost_sep = self.config.cost_separator or ""

        paths = {
            "git": f"{report}{code_sep}/{code}/{repo_name}/git",
            "sizes": f"{report}{code_sep}/{code}/{repo_name}/sizes",
            "pygount": f"{report}{code_sep}/{code}/{repo_name}/pygount",
            "stats": f"{report}{code_sep}/{code}/{repo_name}/stats",
            "findings": f"{report}{code_sep}/{code}/{repo_name}/findings",
            "dependencies": f"{report}{code_sep}/{code}/{repo_name}/dependencies",
            "costs": f"{report}{cost_sep}/costs",
            "instances": f"{report}{cost_sep}/instances",
            "utilization": f"{report}{cost_sep}/instance_utilization",
            "storage": f"{report}{cost_sep}/storage",
            "scan_id": f"{report}{code_sep}",
            "logs": f"{report}/agent_logs",
            "err_stats": f"{report}/agent_err/stats_err",
            "err_findings": f"{report}/agent_err/findings_err",
        }

        if report is None:
            raise Exception("Invocation Error: must supply either a report ID or UUID")

        requires_code = ["git", "sizes", "pygount", "stats", "findings", "dependencies"]

        if path_type in requires_code and code is None:
            raise Exception(f"Invocation Error: type {path_type} requires code")

        if path_type in requires_code and repo_name is None:
            raise Exception(f"Invocation Error: type {path_type} requires repo_name")

        return_path = paths[path_type]

        # logs never gets uuid prefix
        if self.config.uuid and path_type != "logs":
            return_path = "uuid/" + return_path

        if self.config.prefix is not None:
            return_path = self.config.prefix + return_path

        return return_path
