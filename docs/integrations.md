# Integration choices

## Terminal agents

The lightweight base keeps `tmux`; it is a terminal multiplexer, not an agent. `scripts/demo-agent.sh` shows how an automation can create a named demo session and send a harmless synthetic command. It refuses session names outside the fixed `demo` namespace.

For a real agent, choose one after installing the system:

1. **OpenHands**: open-source self-hostable agent framework with terminal-capable runtimes and multiple model-provider choices. Install its supported runtime outside this base image. Review filesystem/network permissions and run it as an unprivileged user. Do not grant it host home directories wholesale.
2. **Claude Code**: optional terminal agent that can be run within tmux. Install from official vendor instructions and authenticate interactively in the user account. The image includes no CLI, login state, or account credential.

Either can operate in a user-owned tmux session. Keep a separate session per task; use a disposable working directory; review commands before granting broad access. The sample wrapper uses only `tmux send-keys` against `demo` and is not an unrestricted remote control endpoint.

## Slack

The default `scripts/slack-mock.py` reads `fixtures/slack-events.json`; it makes no network calls and emits no message. This tests event parsing with synthetic data.

For an optional real integration, build a Slack app from official Slack docs and use Bolt or Socket Mode. Create a bot token only in the operator's Slack workspace, add the minimum bot scopes for the intended operation, and deliver the token at runtime through a root-readable secret file or OS credential manager. Do not store it in this repository or image. Socket Mode avoids a public inbound listener but still requires a protected app-level token and outbound network. Enable the adapter only after an explicit review of the scopes, event subscriptions, destination channels, and retention policy. This demo intentionally ships no live adapter or credentials.
