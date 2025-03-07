from typing import List, Optional, Dict, Any
from modernmetric import process_diff_content
from verinfast.utils.utils import std_exec


class MetricArgs:

    def __init__(self):
        self.ignore_lexer_errors = True
        self.dump = False


def analyze_git_diff(
    commit_id: str, file_name: str, log=None
) -> Optional[Dict[str, Any]]:

    cmd: List[str] = ["git", "show", "-p", "--format=", commit_id, "--", file_name]

    try:
        # Get diff output using std_exec
        diff_output = std_exec(cmd, log=log)

        # We're skipping the first 4 lines of git diff output
        # because they only contain metadata
        diff_lines = diff_output.splitlines()[4:]

        # Separate added and deleted lines
        added_lines = []
        deleted_lines = []

        for line in diff_lines:
            # Skip diff header lines that start with @
            if line.startswith("@"):
                continue
            # Added lines start with +
            elif line.startswith("+"):
                added_lines.append(line[1:])
            # Deleted lines start with -
            elif line.startswith("-"):
                deleted_lines.append(line[1:])

        added_content = "\n".join(added_lines)
        deleted_content = "\n".join(deleted_lines)

        args = MetricArgs()

        added_results = process_diff_content(
            _content=added_content, _file=file_name, _args=args, _importer={}
        )

        deleted_results = process_diff_content(
            _content=deleted_content, _file=file_name, _args=args, _importer={}
        )

        # Combine metrics
        combined_metrics = {}
        for metric_name, added_value in added_results[0].items():
            deleted_value = deleted_results[0].get(metric_name, 0)
            combined_metrics[metric_name] = added_value + deleted_value

        return {
            "metrics": combined_metrics,
            "file": file_name,
            "language": added_results[2],  # same language 4 added and deleted
            "store": {"added": added_results[4], "deleted": deleted_results[4]},
        }

    except Exception as e:
        if log is not None:
            log(tag="git_metrics Error", msg=f"Error analyzing git diff: {str(e)}")
        else:
            print(f"Error analyzing git diff: {str(e)}")
        return None
