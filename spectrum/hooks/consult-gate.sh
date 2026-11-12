#!/bin/sh
# Runs before every Read, Grep, Glob, Bash and MCP call, so with the gate off it exits
# before a Python interpreter starts.
case "${SPECTRUM_CONSULT_GATE:-${CLAUDE_PLUGIN_OPTION_CONSULT_GATE:-}}" in
  true | 1 | on | yes) exec python3 "$(dirname "$0")/spectrum_hooks.py" consult-gate ;;
esac
exit 0
