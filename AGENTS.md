# Agent Operating Notes

## Pull Requests

- The agent is allowed to create pull requests when implementation work is ready and verified.
- The agent is allowed to merge pull requests when the user has asked it to continue integration work or has otherwise approved PR operation.
- Before merging any PR, the agent must inspect Copilot review feedback and any Copilot-reported issues.
- Copilot feedback must be evaluated technically, not applied blindly.
- If Copilot identifies a correctness, security, data-loss, auth, deployment, or test-blocking issue, address it before merging and rerun relevant verification.
- If Copilot feedback is low-risk, stylistic, redundant, or not immediately necessary, the agent may proceed, but should note the reason in its summary.
- Do not merge with failing required checks unless the user explicitly approves the risk.
- Do not force-push or use destructive git operations unless the user explicitly requests them.
