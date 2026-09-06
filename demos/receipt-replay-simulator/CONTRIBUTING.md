# Contributing to the Receipt Replay Simulator

Thanks for helping improve the public AgentLink reliability demo.

This directory is intentionally small, inspectable, and independently licensed under the MIT License. Contributions should keep it that way.

## Good contributions

Useful changes include:

- additional failure / recovery scenarios
- stronger tests for idempotency and reconciliation behavior
- clearer examples of interrupted execution
- portability improvements that keep the demo dependency-light
- documentation fixes that make the reliability model easier to reproduce
- bug reports with a minimal reproduction

## Scope boundaries

Please do not add:

- credentials, tokens, private URLs, or production infrastructure details
- private AgentLink implementation code
- assumptions that a timeout or missing response proves an external action failed
- automatic retries that could duplicate external side effects
- authentication bypasses or credential guessing

The simulator follows a conservative rule: an unknown outcome is not automatically a failed outcome. Reconcile durable evidence before retrying a potentially completed side effect.

## Running the demo

```bash
cd demos/receipt-replay-simulator
python3 demo.py
python3 -m unittest -v
```

Please run the tests before opening a pull request.

## Opening an issue

For bugs or reproducibility problems, include:

1. Python version and operating system
2. exact command you ran
3. expected behavior
4. observed behavior
5. the smallest scenario that reproduces the problem

Never include secrets, customer data, private logs, or internal endpoints.

## Pull requests

Keep pull requests narrow. A good PR explains:

- which reliability behavior changes
- why the change is safe
- which tests cover it
- whether any existing scenario semantics changed

If you add a new decision branch, add a test for it.

## License

By contributing to files in this demo directory, you agree that your contribution is provided under the MIT License contained in this directory.
