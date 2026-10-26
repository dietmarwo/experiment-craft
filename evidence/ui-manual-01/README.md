# UI manual documentation evidence

Documentation-only checks on `main` at `c7cff20`, the merged UI-01 review. See the
[user manual](../../docs/ui-user-manual.md) and the
[implementation log](../../implementation-log.md#ui-user-manual).

- `github-heads.json`: public experiment-craft base and four native heads;
  the accepted lock matches. No native pin moved.
- `unit-and-docs.json` / `.log`: the 140 unit, schema and link tests.
- `manual-validation.json`: shell syntax and installed CLI help checks,
  image dimensions/hashes, byte equality with the accepted review/base,
  and the current web assets' equality with the captured review.

The screenshots and their rendered-browser report are inherited
[UI-01 review evidence](../ui-01-review/README.md). They show actual Chromium
against ten real native jobs, including a touch viewport, not a physical phone.
No image was edited or synthesized. No new browser, native, remote-host or
CI acceptance is claimed for this documentation change. Earlier evidence
is unchanged. Absolute paths refer to the container that ran the checks.
