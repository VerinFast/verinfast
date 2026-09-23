# reporting/ — Claude notes

- **Consume a `ScanResult` argument.** Never reach for shared state. v1's
  module-level `template_definition` is exactly the bug being fixed here
  (`D5`).
- **Render every target.** A multi-repo scan gets a section per repository;
  v1 overwrote each repo's entries with the next one's and showed only the
  last, with no warning.
- **Vendor the CSS.** An offline report that needs a CDN is not an offline
  report (`F17`).
- **Let rendering errors surface.** A swallowed template exception is
  invisible; at minimum log it with the traceback (`D17`, `N10`).
- **Never put source code in the report beyond what the findings already
  carry**, and respect the truncation setting when they do (`S2`).
- `run_summary` is what ATD and the CLI both read to decide whether a scan
  succeeded. Keep `ok` meaning "nothing failed", never "no findings" (`F18`).
