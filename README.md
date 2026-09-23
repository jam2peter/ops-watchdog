# JamPeter Ops Watchdog

JamPeter Ops Watchdog is the decision and deduplication module for the
**OBSERVE** layer of the JamPeter Ops Stack.

It consumes sanitized state snapshots from Audit and Monitor, compares them with
the previous known state and decides whether a human notification is warranted.

It does not repair systems.

## Role

```text
JamPeter Ops Audit ------\
                         +--> Ops Watchdog --> NOTIFY or SILENT
JamPeter Ops Monitor ----/
```

## Behavior

```text
first observation
=> create baseline
=> SILENT

same state
=> SILENT

PASS -> DEGRADED
=> NOTIFY / worsened

DEGRADED -> PASS
=> NOTIFY / recovered
```

The engine namespaces systems by source, so an Audit check and a Monitor check
may use the same local ID without colliding.

## Quick start

```bash
python3 src/ops_watchdog.py \
  --source audit=examples/audit-snapshot.json \
  --source monitor=examples/monitor-snapshot.json \
  --state watchdog-state.json \
  --output watchdog-decision.json \
  --write-state
```

On the first run, the state file becomes the baseline and no alert is emitted.

## Output

The decision contains:

- `notify`: whether a state transition exists;
- `reason`: baseline, no change or state change;
- `events`: normalized transitions;
- `state`: the next deduplication baseline.

Notification delivery is intentionally separate. This repository decides
**whether** to alert; it does not require email, Telegram, Slack or any other
provider.

## Security

- sanitized snapshots only;
- no credentials;
- no raw logs;
- no automatic remediation;
- no arbitrary shell or remote administration;
- no notification provider dependency.

## JamPeter Ops Stack

```text
OBSERVE
├── AUDIT   -> JamPeter Ops Audit
├── MONITOR -> JamPeter Ops Monitor
└── ALERT   -> JamPeter Ops Watchdog
```

## Tests

```bash
python3 -m compileall -q src tests
python3 -m unittest discover -s tests -v
```

## Status

Initial public product: generic source-only transition engine. Runtime adoption
is explicit and separate from source validation.

## License

MIT
