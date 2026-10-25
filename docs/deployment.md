# Local default and planned multi-node configuration

P7 adds a strict offline inventory and a native CLI plan. It prepares more than
one node without claiming that real remote execution is commissioned. Rust
optimization-jobs continues to own SSH, node identity, staging, execution and
allocation. Python does not add a scheduler or transport.

## Templates and defaults

- [local.json](../examples/deployment/local.json) contains one local test node.
- [home-lab.json](../examples/deployment/home-lab.json) adds six disabled SSH
  workers, with planned 16 CPU slots and 128 GiB each.

Both use `default_node: "local-test"`, one local admission slot and explicit
`foreground` mode. The coordinator/main desktop is excluded from the worker
pool. Its local test node is an explicit small test target, not fleet membership.
The SSH hosts, user, key paths and install prefixes are examples to replace.
No SSH private key or host-key material is stored in the configuration.

The versioned [inventory schema](../experiment_craft/schemas/deployment-0.1.schema.json)
defines `experiment.deployment/0.1`. Every path is explicit and absolute;
environment variables and tildes are not expanded. Names, endpoint/root
duplicates, unsupported fields, automatic placement and unsafe SSH helper or
known-hosts paths fail validation. Local foreground roots may contain spaces;
the existing systemd dollar restriction remains in force.

`declared.cpu_slots` is the owner's proposed native admission capacity, and
`declared.memory_bytes` is inventory information. Neither proves physical-core
mapping, available memory, affinity or enforcement. The generated native
`node init` command sets CPU admission capacity; this runtime has no matching
memory-limit option. Measure and reserve service headroom during commissioning.

## Validate and export without contacting any node

```bash
experiment-craft deployment-check examples/deployment/home-lab.json
experiment-craft deployment-export examples/deployment/home-lab.json --destination /absolute/new/deployment-plan
```

Validation checks structure and policy only. Export atomically creates a new
directory with `deployment.json`, `plan.json` and a README; it refuses existing
destinations. The [plan schema](../experiment_craft/schemas/deployment-plan-0.1.schema.json)
defines `experiment.deployment.plan/0.1` and explicitly says
`offline_structure_only`, `runtime_contacted: false` and
`commands_executed: false`.

Each node contains literal argument arrays:

| Field | Where the owner runs it | Meaning |
|---|---|---|
| `setup_on_node` | That node | Native `node init` and explicit worker registration |
| `register_on_coordinator` | Coordinator | Native `fleet nodes add` with explicit SSH endpoint/helper/known-hosts/key paths |
| `probe_on_coordinator` | Coordinator | Native `fleet nodes probe` |

These arrays are instructions, not a shell script. Nothing runs automatically.
Disabled entries remain templates, even though their future commands can be
inspected. The export does not initialize nodes, enable commands, register
workers/endpoints, connect over SSH, accept a host key or alter systemd/lingering.
Registration itself is a native operation that performs authenticated discovery
and pins a real node ID; an inventory entry does not replace that observation.

## Use the local configuration now

Edit the coordinator's runner, the local root and worker executable paths for
your actual installation. The native node must already be initialized and the
needed workers registered by its owner. Then:

```bash
experiment-craft init campaign.json --workspace /absolute/new/campaign --deployment /absolute/deployment.json
experiment-craft continue --workspace /absolute/new/campaign
```

`--node local-test` is optional. Another local test target can be selected
explicitly. `--mode` can override the configured local mode; without a
configuration the existing `--runner`, `--node-root` and systemd default keep
their old behavior. Mixing direct paths with `--deployment`, or using `--node`
without a deployment, is refused.

`allow_commands` is an additional client policy and the proposed native setup
flag. A deployment that says false refuses command manifests even when the node
itself has commands enabled. Setting it true does not enable the node: the
manifest and actual runtime still need their own explicit command opt-ins.

The chosen local runner/root/mode binds through the existing runtime identity
contract. A changed configuration cannot rebind an accepted workspace. Disabled
nodes give `node_disabled`; enabled remote campaign targets give
`unsupported_placement`. Remote campaign routing is not implemented by adding
this inventory. The existing native fleet CLI remains available for explicitly
commissioned endpoints, with its own durable-launch preflight and recovery rules.

## Activate workers later

Follow [January commissioning](january-commissioning.md) on one worker before
two, then six. Install exact pinned native artifacts on each host; verify the
user manager, lingering, resource behavior and SSH identity/known-hosts policy.
Replace the placeholder host/user/paths and deliberately enable only the worker
being commissioned. Run its reviewed setup commands on that host, then use the
native registration/probe commands from the coordinator. Keep its node ID and
artifacts stable across upgrades. Do not move uncertain attempts to another node.

This package tests one actual local runtime. Offline validation covers the
seven-node inventory and generated CLI syntax. It does not validate independent
hosts, host authentication, logout/reboot, cgroups or automatic placement.
RT-07/RT-08 remain the [backend gate](backend-gate.md).
