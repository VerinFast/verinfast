# tests/v2/ — Claude notes

- **Never weaken `test_public_api.py` to make a change pass.** Those tests are
  the reason v2 exists. If one fails, the code is wrong, not the test.
- **The subprocess tests must stay subprocesses.** Checking "importing does
  not read argv" inside pytest proves nothing — pytest has already imported
  the module and owns `sys.argv`.
- **`test_golden_case_matches_atd` is shared with another repository.** If it
  fails, either this side drifted or ATD's did; find out which before
  changing anything.
- Tests run offline. No network, no cloud credentials, no `npm`/`gem`/
  `composer`, no real repositories to clone (`N16`).
- Add a route to `transport/paths.py` → add a case here in the same PR.
- v1's fixtures under `tests/fixtures/` are good and should be reused when the
  dependency walkers are ported; don't write new ones from scratch.
