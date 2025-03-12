import contextlib
import io
import json
import os
from pathlib import Path
import platform
import time

import semgrep.commands.scan as semgrep_scan
from cachehash.main import Cache

from verinfast.config import Config
from verinfast.utils.utils import truncate_children


def run_scan(
    path: str,
    repo_name: str,
    config: Config,
    cache: Cache,
    upload,
    template_definition: dict,
    log=print,
) -> None:
    path = str(Path(path).absolute())
    log(f"path: {path}")
    uname = platform.uname()
    system = uname.system

    if not config.runScan:
        return

    if system.lower() == "windows":
        log(
            """
        Windows does not support Semgrep.
        Please see the open issues here:
        https://github.com/returntocorp/semgrep/issues/1330
                    """
        )

        return

    findings_file = os.path.join(config.output_dir, f"{repo_name}.findings.json")

    custom_args = ["--config", "auto", "--json", f"--output={findings_file}", "-q"]

    findings_success = False
    if not config.dry:
        # if cache exists write cache to findings file
        start_time = time.time()
        cache_results = cache.get(path)
        first_duration = time.time() - start_time
        log(f"cache get took: {first_duration:.2f} seconds")

        if cache_results:
            log("CACHE HIT")
            with open(findings_file, "w") as f:
                f.write(json.dumps(cache_results))
                findings_success = True

        # else run scan
        else:
            log("cache miss")
            log(msg=repo_name, tag="Scanning repository", display=True)
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    semgrep_scan.scan(custom_args)
                    findings_success = True
            except SystemExit as e:
                if e.code == 0:
                    findings_success = True
                else:
                    log(tag="ERROR", msg="SystemExit in Semgrep")
                    log(e)
            except Exception as e:
                log(tag="ERROR", msg="Error in Semgrep")
                log(e)

            # set cache
            # Only try to cache if scan was successful and file exists
            if findings_success and os.path.exists(findings_file):
                try:
                    # Try to cache the results
                    with open(findings_file) as f:
                        results = json.load(f)
                        cache.set(path, results)
                except Exception as e:
                    log(tag="Cache Error", msg=f"Failed to cache results: {str(e)}")

        if findings_success:
            try:
                with open(findings_file) as f:
                    findings = json.load(f)

                # This is on purpose. If you try to read same pointer
                # twice, it dies.
                with open(findings_file) as f:
                    original_findings = json.load(f)

                if config.truncate_findings:
                    # Exclusions are set to exclude fields that are not code
                    truncation_exclusion = [
                        "cwe",
                        "owasp",
                        "path",
                        "check_id",
                        "license",
                        "fingerprint",
                        "message",
                        "references",
                        "url",
                        "source",
                        "severity",
                    ]
                    log(tag="TRUNCATING", msg=f"excluding: {truncation_exclusion}")
                    try:
                        findings = truncate_children(
                            findings,
                            log,
                            excludes=truncation_exclusion,
                            max_length=config.truncate_findings_length,
                        )
                    except Exception as e:
                        log(tag="ERROR", msg="Error in Truncation")
                        log(e)
                        log(json.dumps(original_findings, indent=4, sort_keys=True))
                with open(findings_file, "w") as f2:
                    f2.write(json.dumps(findings, indent=4, sort_keys=True))
                template_definition["gitfindings"] = findings
            except Exception as e:
                if not config.dry:
                    log(tag="ERROR", msg="Error in findings post-processing")
                    log(e)
                else:
                    log(
                        msg=f"""
                            Attempted to format/truncate non existent file
                            {findings_file}
                        """
                    )
        else:
            log(msg="Scan Findings failed")

    # End if findings_success is True

    # Upload findings always, in case of dry run
    # .upload checks should_upload
    upload(file=findings_file, route="findings", source=repo_name)
