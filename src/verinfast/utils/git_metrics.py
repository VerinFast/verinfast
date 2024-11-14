from typing import List, Optional, Dict, Any
from modernmetric import process_diff_content
from verinfast.utils.utils import std_exec

class MetricArgs:
    def __init__(self):
        self.ignore_lexer_errors = True
        self.dump = False
        self.halstead_bug_predict_method = "default"
        self.maintenance_index_calc_method = "default"

def analyze_git_diff(commit_id: str, file_name: str, log=None) -> Optional[Dict[str, Any]]:
    cmd: List[str] = [
        "git", "show", "-p", 
        f"--format=", 
        commit_id, 
        "--", 
        file_name
    ]
    
    try:
        diff_output = std_exec(cmd, log=log)
        
        # Skip the first 4 lines (diff headers)
        diff_lines = diff_output.splitlines()[4:]
        diff_content = '\n'.join(diff_lines)
        
        args = MetricArgs()
        
        results = process_diff_content(
            _content=diff_content,
            _file=file_name,
            _args=args,
            _importer={}
        )
        
        return {
            'metrics': results[0],
            'file': results[1],
            'language': results[2],
            'store': results[4]
        }
        
    except Exception as e:
        if log is not None:
            log(tag="git_metrics Error", msg=f"Error analyzing git diff: {e}")
        else:
            print(f"Error analyzing git diff: {e}")
        return None 