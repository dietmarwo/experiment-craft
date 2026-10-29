# Local experiment dashboard

For a step-by-step walkthrough with real screenshots, start with the
[UI user manual](ui-user-manual.md). This page is the behavior and verification
reference.

The 0.4.0 client adds a browser UI over existing initialized local
campaigns. Start/continue, pause, reconciliation, stop and collection use the
same campaign functions and native handles as the CLI. The dashboard observes
saved campaign state; it is not a second execution service or capacity ledger.

## Start with an existing experiment

Initialize the campaign with the existing CLI and declare any scientific
comparison before starting it. Then run:

```bash
experiment-craft dashboard --workspace /absolute/campaign --state-dir /absolute/dashboard-history
```

Open the `url` in the printed JSON. It includes a temporary access token in its
fragment. The browser moves it into tab session storage and removes the fragment
from the address bar. Refreshing that tab keeps access. A new server process
generates a new token: open the newly printed URL, in the same tab or a new one. No external fonts, scripts,
chart service or build tool is needed. The wheel includes the HTML, CSS and JS.

Repeat `--workspace` to attach up to 32 initialized campaigns. An optional
`--deployment /absolute/deployment.json` labels local roots and shows configured
workers. It is an informational inventory overlay, not a new authority over an
already bound campaign. Disabled workers show no invented history. Enabled SSH
entries still have no Python remote campaign routing. Multiple real local node
roots can be observed independently; this does not establish multi-host execution.

The UI attaches only the workspaces explicitly named at startup. It cannot
browse arbitrary paths, upload a script, edit a manifest, initialize a node,
register workers, change an inventory or move a campaign to another node.
Campaign creation and protocol declaration remain CLI operations in this first UI.

## Try a prepared local example

With the exact pinned native binaries built using the [README](../README.md):

```bash
python3 examples/dashboard/prepare.py --bin-dir /absolute/native/bin --output /absolute/new/dashboard-demo --serve
```

The script explicitly administers a fresh one-slot foreground test node and
initializes a ten-step campaign; it submits nothing until **Start** is pressed.
There are four visible two-second checkpoint commands, four seeded sphere runs,
one LP/IP solve and one SQP solve. The checkpoint commands let you try controls
while work is in flight. Their time is not described as solver work. The inventory
shows this local node and the six disabled worker templates. The coordinator is
not a worker. Without `--serve`, the script prints the literal dashboard argv.

## Controls and their meaning

| Control | Behavior |
|---|---|
| Start / Continue | Calls existing advancement one step at a time until finished, paused, stopped, uncertain or an error occurs. Native admission and the existing absolute deadline apply. |
| Pause dispatch | Commits the cooperative pause even while a foreground job is running. An already committed launch can finish. It does not cancel active work. A running Start/Continue ends after the current step, without an error, also when the pause comes before its first dispatch. |
| Reconcile & unpause | Verifies the original runtime/worker identities and all saved handles through the existing operation. Unknown/divergent work stays paused. It does not start pending steps; press Continue separately. |
| Stop | After a confirmation naming the campaign and its workspace path, commits stop and requests native cancellation. Pending steps become `stopped`. An acknowledgement is not proof of termination; observe the outcome. |
| Refresh native state | Calls `collect_now` once. It observes existing handles without dispatching; another advancing client can return `campaign_busy`. |

Controls return HTTP 202 for an accepted background operation, not a completed
experiment. The UI displays operation failures and native error codes. Control
and advancement have separate lanes, so a long foreground call does not prevent
pause or stop. Repeated starts while the same UI operation runs return 409
`operation_busy`. While the dashboard shuts down, or when the process cannot
start another operation thread, actions return 503 (`dashboard_stopping`,
`dashboard_busy`); nothing was started, and the action can be tried again.
The existing campaign locks, intent transactions and no-replay checks still apply
to simultaneous CLI access. Do not operate multiple writable recovered copies.

The page refreshes every two seconds. It leaves an unchanged experiment panel
as it is, so a selection survives, and otherwise keeps the details block open
and the step table's scroll position.

Closing a browser tab does not stop the dashboard process or its advancement.
Restarting the dashboard never automatically starts, resumes, cancels, repairs
or unpauses a campaign.

Ctrl-C and SIGTERM stop the dashboard the same way. It refuses new actions at
once, ends advancement between steps, closes open browser connections and waits
for campaign calls in flight. While the dashboard serves, it starts runner calls
in their own session, so a terminal's Ctrl-C does not reach the native job in
flight: that job completes, and the next step stays pending. Use Stop first if
cancellation is wanted. (The `run` and `continue` commands keep the runner in
the terminal's process group, so Ctrl-C there also reaches the runner.)

After its readers and writers finish, the dashboard requests a SQLite checkpoint
and WAL truncation without new decisions. External readers can retain WAL
pages. The shutdown JSON lists checkpoint errors (such as a busy reader or a
missing workspace), and the command then exits with status 1. It never reports
campaign success merely because the web server stopped. A hard-killed dashboard
leaves recovery to the existing native-handle rules. Service, logout and reboot
guarantees are unchanged and remain uncommissioned.

## Artifacts and recorded certificate audits

Select an experiment, then press **Load artifacts** in **Artifacts & recorded
audits**. Nothing is loaded or collected automatically. The catalog shows up
to 100 declared command outputs per page; **Previous outputs** and **Next
outputs** traverse the immutable plan order. Byte counts and digests stay
unknown until the native result seals a file. Refresh native state first when
an external driver has completed work, then refresh artifacts separately.

- **Collect** retains one sealed output through the existing bound runtime.
  It shares the advancement lane with Start/Continue and Refresh native state.
  Pause and Stop remain responsive. Like those advance controls, it is disabled
  while the observer is stale or failed or progress history is unavailable.
  Collection is allowed while paused and does not create a job, change campaign
  decisions or run a checker. Repeating it checks the retained copy offline.
  While a collection is in progress, the catalog, View audit and the report
  downloads wait for it. If the dashboard stops reporting the collection,
  because another operation took its place or the dashboard restarted, the
  panel says so; refresh the artifacts to see its result.
- **Download** serves that retained file after checking its length and digest
  again. It does not collect an unretained file. Binary files are downloaded
  as attachments and are never embedded as HTML.
- **View audit** reads the selected output as the supported CAP acceptance
  receipt. For a sealed receipt, collect it first. The adapter requires the
  application's generated search → audit → acceptance shape, including its
  admitted checker inputs. Other command shapes return
  `unsupported_verification`; a well-formed receipt alone is insufficient.

The audit panel keeps the application's recorded verdict separate from the
native step/state/exit code. `reported_accepted`, `reported_rejected`,
`unconfirmed` and `unavailable` retain the CLI meanings. An accepted receipt
alongside a failed command is unconfirmed. Missing receipts keep counts and
costs unknown. Every arm remains in protocol order, including failed and
right-censored observations; no ranking or successful-only statistic is added.
Accounted seconds are the adapter's final-candidate composite observation, not
a time to first certificate or a machine utilization measurement.

**Download JSON**, **Download Markdown** and **Download CSV** use the same
checked rendering as `verification-report`. They re-read and validate the
retained inputs and receipt at download time without publishing a directory
or accepting a filesystem path from the browser. The trust boundary is
unchanged: the report checks the recorded application chain; it does not
execute an independent checker, prove a theorem, or verify the node's named
interpreter/search executable.

Results refresh only on explicit request and display their read time. The
normal two-second status poll does not transfer artifact bytes or silently
replace an audit. Loaded results remain labelled as retained observations
when connection/state is unavailable. A failed read clears the corresponding
view; changed/symlink caches are refused without repair. Remove a corrupt
cached copy and collect it again using the [artifact guide](verification-reports.md).
No arbitrary workspace, input path or download destination can be supplied.

## Progress and history

Each node chart aggregates only its attached campaigns. It plots counts of
accepted steps, other finished steps, uncertain steps and pending steps using
the dashboard's observation timestamps. Other finished includes failed,
cancelled, blocked, stopped and budget-exhausted steps. A step accepted under
its declared policy does not gain a stronger mathematical claim in the UI.
The table preserves individual statuses and exposes errors and recent decisions.

The displayed unresolved declared slots sum requests in dispatching, active and
unknown states. They are neither measured CPU use nor a schedulable capacity
calculation. Queued, starting and uncertain work may be included. Inventory
capacity is configured information, not a measured limit. This version has no
CPU/RAM/GPU telemetry, within-job percentage, objective convergence curve or ETA.

History starts when this dashboard first observes a workspace. It does not
reconstruct historical states from incomplete event payloads. The observer runs
even when no browser is open, but makes no runtime calls: externally driven or
detached jobs require their driver or an explicit Refresh native state to update
the campaign's saved observations. “Connected” refers to the browser/dashboard
connection, not node reachability. Nodes are not automatically probed.

State is sampled every two seconds by default (`--sample-seconds`, 0.25..60).
Changed totals and a heartbeat at least every 30 seconds are retained. Sampling
can miss short intermediate states; this is not an exact execution timeline.
Each restart and backward clock jump starts a new line segment. Missing campaign
state produces a gap, never zero counts. Browser connection failure disables
controls. A stale or failed observer disables advancement but keeps Pause/Stop
available when campaign state can still be read; read errors keep details visibly
marked stale. Long observation gaps are not connected by chart lines: a line
joins two points at most 60 seconds or three sampling intervals apart, using
the current `--sample-seconds`. History recorded with intervals above 20 seconds
therefore shows as separate points when viewed with a shorter interval.

The separate `history.sqlite3` keeps the latest 2,000 points per node/campaign-set
scope (`--history-limit`, 10..10,000). It does not grow indefinitely in row count.
Changing the set of attached campaigns changes the scope; inactive scopes are
removed at startup rather than joining unlike totals. Removing a campaign from
the dashboard can therefore remove its old aggregate history. SQLite may retain
allocated pages after trimming. The chart's times use the browser timezone.
Download history exports the retained raw points as JSON.

Keep `--state-dir` outside all campaign/native trees. It is a disposable
observation cache, not part of the authoritative campaign backup. Restart with
the same directory to keep history; one dashboard process may use it at a time.
Campaign backup, restore and native-root recovery stay unchanged. To preserve
the UI cache separately, stop the dashboard and copy its directory.

## Local access and limits

The server listens only on `127.0.0.1` (`--port 8765`, or 0 for an assigned port).
A port that is already in use fails with `port_unavailable` before the history
directory is created or changed. API reads and controls require the temporary
token; writes also check Origin, Host, JSON shape and body bounds. There is no
CORS permission or external asset. Do not put the token in a shared log. The
browser may keep the opened URL, token included, in its list of visited pages;
the token is valid only until that dashboard process stops. This
standard-library HTTP service is for a trusted local operator, not public
hosting or a multi-user authentication boundary. A local trusted application
with the token can use the same controls.

Each refresh transfers the complete snapshot: every step of every attached
campaign and its 30 most recent decisions. Campaigns with many thousands of
steps make every refresh correspondingly large, and a refresh that takes longer
than eight seconds shows the page as disconnected; attach fewer of them at once.
Each browser connection is served by its own thread, which suits one operator
with a few tabs, not many simultaneous clients.

There is no bind-to-LAN flag. Phone access to a running coordinator requires
a separately secured tunnel/proxy and its own commissioning; none is installed
or claimed here. The screen adapts to phone-sized browsers. Real remote
campaign routing, node probes/telemetry, automatic placement, durable background
service management, roles and a browser manifest editor remain future work.

## Verification

Unit tests cover the HTTP/token/origin boundary, path and duplicate-copy
refusals, bounded history, missing state and the versioned outputs. The required
real-runner integration suite covers start/pause/unpause, cancellation during a
foreground run, restart without launch, uncertain intent without replay,
separate local node identities, and Ctrl-C sent to the dashboard's process
group or SIGTERM during a run.

The DOM interaction test uses the real HTTP server and all three actual solver
workers. It clicks controls, checks errors/disconnection, SVG paths, history
download and exact native job counts. It is deliberately not described as a
browser layout test. Run with Node 24 and the locked development-only jsdom and
Playwright dependencies (not needed to install or run the dashboard):

```bash
npm ci --prefix tests/ui --ignore-scripts
NODE_PATH="$PWD/tests/ui/node_modules" \
  EXPERIMENT_CRAFT_TEST_BIN_DIR=/absolute/native/bin \
  EXPERIMENT_CRAFT_TEST_PYTHON=/absolute/venv/bin/python \
  node tests/dashboard_dom.cjs /absolute/new/ui-test
```

CI runs this interaction test after building the native binaries.

`tests/dashboard_browser.cjs` checks the rendered page in a real Chromium at
phone (390 × 844, touch) and desktop (1366 × 900) sizes. It prepares the example,
serves it, and checks that the token leaves the address bar and that a token
URL pasted into the open tab is taken, that nothing overflows horizontally,
that the stop dialog names the experiment and its workspace, fits and can be
dismissed or confirmed, that keyboard focus is visible, that Start completes
all ten real jobs without console errors, and that the details block and the
step table keep their state while the page refreshes. It writes `report.json` and
screenshots to a new directory, and checks that the dashboard then shuts down
cleanly. CI runs it after the interaction test. Locally, after the `npm ci`
above:

```bash
tests/ui/node_modules/.bin/playwright install chromium
NODE_PATH="$PWD/tests/ui/node_modules" \
  EXPERIMENT_CRAFT_TEST_BIN_DIR=/absolute/native/bin \
  EXPERIMENT_CRAFT_TEST_PYTHON=/absolute/venv/bin/python \
  node tests/dashboard_browser.cjs /absolute/new/browser-check
```

An emulated phone viewport is not a physical phone: touch handling and the
layout on an actual device are still to be checked.

`tests/dashboard_results_browser.cjs` exercises artifact collection, byte-exact
report/raw downloads, all four verdict states, late responses after selection
changes, superseded operations and cache refusal in rendered Chromium. Its
nine real command jobs copy recorded fixtures; it does not execute a scientific
checker. The retained real scalar/PDE report tests check the three report files
against their historical bytes. Run this browser test with the same native
bin/Python/NODE_PATH variables shown above, and a fresh output directory.

The browser tests normally use Playwright's installed Chromium. An existing
compatible Chromium can be selected with `EXPERIMENT_CRAFT_TEST_CHROMIUM` and
an optional JSON argv array in `EXPERIMENT_CRAFT_TEST_CHROMIUM_ARGS`. These are
test-only overrides; neither adds a production browser dependency or changes
the dashboard service.
