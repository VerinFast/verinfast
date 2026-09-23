# reporting/

Turning a `ScanResult` into something a human or a server reads.

| File | What |
| ---- | ---- |
| `html.py` | the offline results page |
| `summary.py` | the machine-readable run summary |

## The local report

`should_upload: false` plus an output directory is a real privacy feature,
not a debug flag — it is how a customer inspects everything before any of it
is sent. The page has to work.

Three things v1 got wrong:

- it rendered a module-level dict, so a multi-repo scan silently showed only
  the last repository;
- it loaded Bootstrap from a CDN, so the "offline report" needed the internet;
- it wrapped rendering in a bare `except:` that logged
  `"Template Creation Failed"` and discarded the exception.

## The run summary

New in v2. v1 gave a caller no way to tell "clean scan, no findings" apart
from "the scan never ran" — both produced an empty findings file. The summary
reports what ran, what was skipped, what failed and why.

## Current state

`summary.py` is implemented. `render_html` is a stub.
