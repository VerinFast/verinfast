---
title: Feature: Host System Info
parent: features
artifact: system_info.json
tags: v2, feature, host
---

# Feature: Host System Info

## What it produces

`system_info.json` in the output directory: OS, OS version/release, machine,
processor, hostname, physical and logical CPU counts, total/available/used RAM,
disk size/used/free, Python version. Collected by
`src/verinfast/system/sysinfo.py::get_system_info` using `platform`, `psutil`
and `shutil.disk_usage("/")`.

## Notes for v2

- It is **not uploaded**. It is written locally and logged. ATD v3 has no
  ingest route for it. Either wire it up or drop it — see [[Open Questions]].
- It contains the **hostname**, which is arguably identifying. If it starts
  being uploaded it belongs under [[Feature: Privacy Controls]].
- `shutil.disk_usage("/")` reports the root filesystem, not the volume holding
  the scan target. On a container that is usually the wrong number.
- A failed write currently raises `RuntimeError` and aborts the whole scan.
  Host metadata is the least important artifact produced; it should never be
  fatal.
