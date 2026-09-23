"""The offline results page.

Ports ``src/verinfast/templates/results.j2`` and ``Agent.create_template``.

Three fixes on the way across:

- **Takes a result, not a global.** v1 rendered a module-level
  ``template_definition`` dict that every stage mutated, which is why a
  multi-repo scan silently showed only the last repository (`D5`).
- **One section per target**, so a multi-repo scan shows all of them.
- **No CDN.** v1 loaded Bootstrap from the network, so the "offline report"
  needed the internet. Vendor the CSS (`F17`).

The rendering exception is also allowed to surface; v1 swallowed it in a
bare ``except:`` and logged "Template Creation Failed" (`D17`).
"""

from __future__ import annotations

from pathlib import Path

from verinfast2.models import ScanResult


def render_html(result: ScanResult, *, out: Path | None = None) -> str:
    """Render the results page. Returns the HTML; writes it if ``out`` is set.

    Raises:
        NotImplementedError: not yet ported.
    """
    raise NotImplementedError("reporting.html.render_html")
