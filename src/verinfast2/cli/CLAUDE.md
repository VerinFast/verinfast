# cli/ — Claude notes

- **This is the only package that may `print()`, prompt or produce an exit
  code.** If something in `core/`, `scanners/` or `cloud/` seems to need one,
  it needs a callback that the CLI supplies instead (`L5`).
- **`main()` returns an int; it does not call `exit()`.** Keeps it testable
  and keeps the library unable to take a process down.
- **No argparse defaults.** A default lands in the namespace looking exactly
  like a user-supplied value and then clobbers the config file (v1's own
  comment says so).
- **Consent is a config field, not a constructor prompt.** v1 called
  `input()` from `Agent.__init__`, which a library can never do.
- **Don't write to `~` on behalf of the library.** Preference storage is a CLI
  concern; `embedded` mode writes nothing there at all (`S15`).
- Progress goes through `ScanContext.progress`, not `print` — the dependency
  walker's hardcoded "Dependency Scan 40%" lines are the anti-pattern (`N11`).
- Keep the flag names v1 shipped (`-c/--config`, `-o/--output`, `--dry`,
  `--should_upload`, `--base_url`, `--uuid`, `--path`, `-t/--truncate`).
  ATD's onboarding instructions and existing customer scripts use them.
