---
name: knowledge
description: >
  Use when a question about this project is about intent or consequence: why
  something exists, what need or feature it serves, what depends on it or
  would break if it changed, which code realizes a feature, which business rule applies,
  or how a feature works in a repository you do not know yet. Answers come from the
  project's Spectrum knowledge graph through its MCP tools.
---

# Consulting Spectrum

Spectrum's MCP server explains its tools in its own instructions and tool descriptions;
this skill adds when a call pays off and how to split a question before making one.

## When Spectrum helps

| Task | Example question |
|---|---|
| Intent — why does this exist, who needs it | "What stakeholder need does the export scheduler serve?" |
| Impact — what depends on it, what breaks if it changes | "What breaks if the order table's status column changes?" |
| Feature ↔ code — which components realize a feature | "Which application components realize invoice approval?" |
| Business rules — which rule constrains a behaviour | "Which business rules constrain account deletion?" |
| Orientation in an unfamiliar repository | "Which components take part in user sign-up?" |

Most questions have two halves. The **intent half** — what a thing is for, who asked for
it, what depends on it — is in Spectrum and nowhere in the source. The **mechanism half**
— which file, symbol or call order implements it today — is in the source, which is exact
and current while the graph is a snapshot that can lag it. Ask Spectrum for the first,
read the code for the second, and confirm in the source anything Spectrum says about code.

## When to skip it

- Symbol lookup and pattern search: Grep is exact and instant.
- Mechanical edits (rename, lint, dependency bump) and tests for code you just wrote.
- Debugging from a stack trace that already points at the problem.

## How to call it

- `query_knowledge` takes **one natural-language question per call**, worded as you
  would ask a colleague. Split a task with several parts into several calls; they can
  run in parallel.
- **Name one thing.** A question about one component, feature or rule returns a
  focused answer; a question about a whole subsystem returns more than the client can
  show.
- Set `complete` only when you need every match: a list you will count, or an absence
  you will claim.
- Every element `id` in a result is a short id. Pass it unchanged to `graph_expand` or
  `graph_subgraph` to follow its links, or to `source_quotes` to see the source text
  behind it.
- **Project:** before the first Spectrum call of a session, make sure the project is
  this repository's; an argless call can land on another project, whose answers describe
  another system. Pass `project_id` when the prompt, `CLAUDE.md` or `AGENTS.md` gives one. Otherwise
  call `list_projects` and compare each name with this repository's folder and git
  remote: when one plainly names it, pass that id on every call. When none plainly
  matches, stop the task, begin your reply with `SPECTRUM PROJECT NOT CONFIRMED:`, name
  the repository and the projects, and ask the user which project belongs to it, or
  whether none does; continue only on their answer. Never invent an id.
