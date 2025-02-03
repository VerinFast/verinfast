import json
import os
import contextlib
import io
import platform

import semgrep.commands.scan as semgrep_scan
from modernmetric.__main__ import main as modernmetric

from verinfast.utils.utils import truncate_children
from verinfast.dependencies.walk import walk as dependency_walk
from verinfast.utils.license import report as report_license


class ScannerTools:
    def _run_stats_scan(self, path, repo_name):
        """Run modernmetric stats scan"""
        stats_input_file = os.path.join(self.config.output_dir, repo_name + ".filelist.json")
        stats_output_file = os.path.join(self.config.output_dir, repo_name + ".stats.json")

        if not self.config.dry:
            self.log(msg=repo_name, tag="Analyzing repository with Modernmetric", display=True)
            filelist = self._get_file_list(path)

            with open(stats_input_file, 'w') as f:
                f.write(json.dumps(filelist, indent=4))

            custom_args = [f"--file={stats_input_file}", f"--output={stats_output_file}"]
            modernmetric(custom_args=custom_args, license_identifier=self.config.reportId)
            report_license(self.config.reportId, self.config, "modernmetric")

            # Load stats into template definition
            try:
                with open(stats_output_file, 'r') as f:
                    self._update_template_definition("stats", json.load(f))
            except Exception as e:
                self.log(tag="ERROR", msg=f"Failed to load stats into template: {str(e)}")

        self.agent.upload(
            file=stats_output_file,
            route="stats",
            source=repo_name
        )

    def _run_semgrep_scan(self, repo_name):
        """Run semgrep security scan"""
        if platform.system().lower() == 'windows':
            self.log("""
            Windows does not support Semgrep.
            Please see the open issues here:
            https://github.com/returntocorp/semgrep/issues/1330
                     """)
            return

        findings_file = os.path.join(
            self.config.output_dir,
            f"{repo_name}.findings.json"
        )

        custom_args = [
            "--config", "auto",
            "--json",
            f"--output={findings_file}",
            "-q"
        ]

        findings_success = False
        if not self.config.dry:
            self.log(msg=repo_name, tag="Scanning repository", display=True)
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    if not self.config.dry:
                        semgrep_scan.scan(custom_args)
                    if os.path.exists(findings_file):
                        # Load and cache findings
                        with open(findings_file) as f:
                            findings = json.load(f)
                            self._cache_findings(findings_file, findings)
                findings_success = True
            except SystemExit as e:
                if e.code == 0:
                    findings_success = True
                else:
                    self.log(tag="ERROR", msg="SystemExit in Semgrep")
                    self.log(e)
            except Exception as e:
                self.log(tag="ERROR", msg="Error in Semgrep")
                self.log(e)

        if findings_success and os.path.exists(findings_file):
            self._process_findings(findings_file)

        self.agent.upload(
            file=findings_file,
            route="findings",
            source=repo_name
        )

    def _cache_findings(self, file_path, findings):
        """Helper method to cache findings"""
        try:
            self.cache.set(file_path, findings)
        except Exception as e:
            self.log(
                tag="Cache Error",
                msg=f"Failed to cache results: {str(e)}"
            )

    def _process_findings(self, findings_file):
        """Process and potentially truncate semgrep findings"""
        try:
            with open(findings_file) as f:
                findings = json.load(f)

            with open(findings_file) as f:
                original_findings = json.load(f)

            if self.config.truncate_findings:
                truncation_exclusion = [
                    "cwe", "owasp", "path", "check_id", "license",
                    "fingerprint", "message", "references", "url",
                    "source", "severity"
                ]
                self.log(
                    tag="TRUNCATING",
                    msg=f"excluding: {truncation_exclusion}"
                )
                try:
                    findings = truncate_children(
                        findings,
                        self.log,
                        excludes=truncation_exclusion,
                        max_length=self.config.truncate_findings_length
                    )
                except Exception as e:
                    self.log(tag="ERROR", msg="Error in Truncation")
                    self.log(e)
                    self.log(json.dumps(original_findings, indent=4, sort_keys=True))

            with open(findings_file, "w") as f2:
                f2.write(json.dumps(findings, indent=4, sort_keys=True))

            # Load findings into template definition
            self._update_template_definition("gitfindings", findings)

        except Exception as e:
            if not self.config.dry:
                self.log(tag="ERROR", msg="Error in findings post-processing")
                self.log(e)
            else:
                self.log(msg=f"Attempted to format/truncate non existent file {findings_file}")

    def _scan_dependencies(self, repo_name):
        """Scan repository dependencies"""
        dependencies_output_file = os.path.join(
            self.config.output_dir,
            f"{repo_name}.dependencies.json"
        )
        self.log(msg=repo_name, tag="Scanning dependencies", display=True)
        if not self.config.dry:
            dependencies_output_file = dependency_walk(
                output_file=dependencies_output_file,
                logger=self.log
            )

            # Load dependencies into template definition
            try:
                with open(dependencies_output_file, "r") as f:
                    self._update_template_definition("dependencies", json.load(f))
            except Exception as e:
                self.log(tag="ERROR", msg=f"Failed to load dependencies into template: {str(e)}")

        self.log(msg=dependencies_output_file, tag="Dependency File", display=False)
        self.agent.upload(
            file=dependencies_output_file,
            route="dependencies",
            source=repo_name
        )
