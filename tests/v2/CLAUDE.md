# tests/v2/ — Claude notes

- **Never weaken `test_public_api.py` to make a change pass.** Those tests are
  the reason v2 exists. If one fails, the code is wrong, not the test.
- **The subprocess tests must stay subprocesses.** Checking "importing does
  not read argv" inside pytest proves nothing — pytest has already imported
  the module and owns `sys.argv`.
- **`test_golden_case_matches_atd` is shared with another repository.** If it
  fails, either this side drifted or ATD's did; find out which before
  changing anything.
- **`atd_fixtures.py` is a hand-maintained copy of ATD's payload shapes.**
  Its odd values are the specification, not sloppiness: numstat `"-"` for
  binary files, an author with no `<email>`, the `"."` sizes root entry, a
  `temp_repo/` path, a bare-string `cwe`. Never "clean them up" — each one
  exists because ATD asserts on it.
- **`test_atd_contract.py` asserts paths copied from ATD's test, not paths
  recomputed from our own code.** That is the whole point: recomputing them
  would pass happily while the wire was wrong.
- **415 must stay out of `RETRYABLE`.** `test_uploader.py` asserts it
  directly. Adding it looks like a reasonable generalisation and would make
  every AV rejection cost three round-trips.
- **Tests run offline, and `conftest.py` enforces it.** An autouse fixture
  patches the socket layer; a test that opens a real connection fails with an
  explanation. Never weaken or opt out of that fixture to make something
  pass — a scanner that needs the network in a test is a scanner that will
  make a customer's scan phone out. Inject an `httpx.MockTransport` or a
  client with `enabled=False`.
- **`subprocess` is monkeypatched to fail in the dependency tests.** That is
  the test proving no package manager is ever run (`S7`); it is not
  incidental.
- Add a route to `transport/paths.py` → add a case here in the same PR.
- v1's fixtures under `tests/fixtures/` are good and should be reused when the
  dependency walkers are ported; don't write new ones from scratch.
