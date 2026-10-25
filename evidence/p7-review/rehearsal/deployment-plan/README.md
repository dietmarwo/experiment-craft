# Deployment preparation

This is an offline plan. No node was contacted, configured or commissioned.
The default is one local test node. Worker entries are explicit future endpoints;
disabled entries are templates, not activation instructions. Commands in plan.json
are literal argument arrays: setup_on_node runs on that node, while registration
and probing run on the coordinator through optimization-jobs. This export does
not execute them, enable automatic placement, copy SSH keys, accept host keys,
or prove resource enforcement. Read the operations/deployment guides and complete
the January commissioning gates before activating real workers.
