# Spectrum plugin for Claude Code, Codex and Copilot

Connects a coding agent to Spectrum, the knowledge graph that holds a project's requirements, business rules, features, design decisions and the code that realizes them. It also teaches the agent when to ask Spectrum, so the agent consults it about intent, impact and business rules before it reads code.

This is the **production** build, talking to `https://mcp.spectrum.labs.jb.gg/mcp`.

## What it ships

- **The Spectrum MCP server** (`query_knowledge`, the graph tools, `source_quotes`, `list_projects`), whose own instructions tell the agent what each tool is for.
- **The `spectrum:knowledge` skill**: when a Spectrum call pays off, how to split a question into its intent and mechanism halves, and how to word a query.
- **Hooks**: a session-start [project check](#choosing-the-project), a one-line reminder beside each prompt to consult Spectrum before reading code, and an opt-in [consult gate](#consult-gate-opt-in), off by default.

What takes effect depends on the host:

- **Claude Code** runs all of it.
- **Codex** runs the plugin's hooks only once you have approved them, and a change to the plugin's files, an update included, withdraws that approval until you give it again. Unapproved hooks do not run; the skill and the MCP server do not depend on them.
- **Copilot** gets the server and the skill. It runs the hooks but does not read their replies, so they deliver neither the project check, the reminder nor the gate's refusal. The skill carries the project-check instruction.

## Install

Claude Code:

```bash
claude plugin marketplace add JetBrains/spectrum-agent-plugins
claude plugin install spectrum@jetbrains-spectrum
```

Codex:

```bash
codex plugin marketplace add JetBrains/spectrum-agent-plugins
codex plugin add spectrum@jetbrains-spectrum
```

Copilot:

```bash
copilot plugin marketplace add JetBrains/spectrum-agent-plugins
copilot plugin install spectrum@jetbrains-spectrum
```

## Keep it up to date

Claude Code updates a marketplace in the background when its settings entry sets `autoUpdate`. Declaring the marketplace and the plugin in settings is the recommended way to install it. Put this in `~/.claude/settings.json` for every project, or in a repository's `.claude/settings.json` for everyone who works in it:

```json
{
  "extraKnownMarketplaces": {
    "jetbrains-spectrum": {
      "source": { "source": "github", "repo": "JetBrains/spectrum-agent-plugins" },
      "autoUpdate": true
    }
  },
  "enabledPlugins": {
    "spectrum@jetbrains-spectrum": true
  }
}
```

A repository's settings register the marketplace once its folder is trusted, and each contributor then runs `claude plugin install spectrum@jetbrains-spectrum --scope project` to install the plugin.

Copilot honours `autoUpdate` from user settings, `~/.copilot/settings.json`, on the `jetbrains-spectrum` entry of `extraKnownMarketplaces`. It ignores the setting in a repository's settings. To update by hand:

```bash
copilot plugin marketplace update jetbrains-spectrum
copilot plugin update spectrum
```

Codex refreshes a marketplace when you run:

```bash
codex plugin marketplace upgrade jetbrains-spectrum
```

## Signing in

Claude Code opens a browser to sign in on the first Spectrum call; `/mcp` shows the server's state and re-runs sign-in. In Codex, `codex mcp login spectrum` opens a browser to sign in.

## Choosing the project

The tools take an optional `project_id`. When the agent omits it, the server asks you to pick one of your projects, and uses it for the rest of the session. If your account can read exactly one project, a client that cannot show the picker — headless `claude --print` or `codex exec`, for example — gets that project. With several projects and no picker, the error lists every project's name and id, and the agent retries with one. Passing `project_id` (in your prompt, `CLAUDE.md` or `AGENTS.md`) fixes the project up front.

In Claude Code, and in Codex once its hooks are approved: at the start of every session, and again after the conversation is cleared or compacted, a hook gives the agent the repository's folder name and git remotes and tells it to confirm the project before its first Spectrum call. With no `project_id` given, the agent calls `list_projects` and passes the id of the project whose name plainly names the repository. When none does, it stops the task, begins its reply with `SPECTRUM PROJECT NOT CONFIRMED:`, and asks you which project belongs to the repository. A headless run ends with that reply; re-run it with the project's id in the prompt.

## Consult gate (opt-in)

In Claude Code, and in Codex once its hooks are approved, the reminder never blocks anything. The consult gate does: once the agent has made several code searches or reads with no Spectrum call in between, it refuses the next one with a reason that names `query_knowledge`. It refuses at most one call per time window, and the refused call goes through when the agent repeats it, so the agent is never stuck.

A search or read is a Read, Grep or Glob call, or a shell command such as `grep`, `rg`, `find`, `cat`, `sed` or `nl`. Codex reads files through shell commands like these, which the gate counts; Read, Grep and Glob are Claude Code's tools.

| Plugin option | Environment override | Default | Meaning |
|---|---|---|---|
| `consult_gate` | `SPECTRUM_CONSULT_GATE` (`on`/`off`) | off | Turn the gate on. |
| `consult_gate_after` | `SPECTRUM_CONSULT_GATE_AFTER` | `3` | Searches let through before a refusal. |
| `consult_gate_window_seconds` | `SPECTRUM_CONSULT_GATE_WINDOW_SECONDS` | `120` | At most one refusal per this many seconds. |

In Claude Code, set plugin options with `/plugin configure spectrum` or `claude plugin configure spectrum@jetbrains-spectrum`. The environment variable wins over the option. It is the only way to set the gate in Codex, which has no plugin options.

## Requirements

`python3` (standard library only) and a POSIX `sh` on `PATH`; `git` for the project check to name the remotes. The hooks read the repository's git config, write only a small per-session state file under the plugin's data directory, and make no network calls.

## License

The plugin is licensed under the Apache License 2.0; see [`LICENSE`](LICENSE).
