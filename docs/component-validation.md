# Component Graph Validation

`tools/validate_component_graph.py` is the repository's executable integrity check for the Lego-component catalog. It validates every `components/**/*.component.json` descriptor and its declared dependency relationships.

## What it catches

- Invalid JSON descriptors
- Missing core contract fields
- Incorrect core-field types
- Missing `events.emits` or `events.listensTo` arrays
- Duplicate component IDs
- Dependencies that do not exist in the component catalog
- Circular dependencies

## Run locally

```bash
python3 tools/validate_component_graph.py
```

To write a machine-readable report:

```bash
python3 tools/validate_component_graph.py --report reports/component-graph.json
```

## Build order

On success, the validator returns `buildOrder`: a topological order in which dependencies appear before the components that need them. A Builder agent can use that result to construct a manifest safely instead of hand-ordering components.

## CI policy

The GitHub Actions workflow runs this validator for every push and pull request. A broken dependency, duplicate ID, malformed descriptor, or cycle blocks the workflow.

This validates the **schema-side graph**. Runtime adapter behavior is separately tracked in `roblox-adapters/ADAPTER_STATUS.md`; a descriptor validating successfully does not imply that a Roblox adapter is implementation-complete.
