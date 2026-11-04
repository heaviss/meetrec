# Wayfinder tracker (local markdown)

- `map.md` — the map (`wayfinder:map`).
- `NN-slug.md` — a ticket, child of the map. Frontmatter:
  - `type`: research | prototype | grilling | task
  - `status`: open | closed
  - `assignee`: empty = unclaimed
  - `blocked_by`: list of ticket numbers
- Frontier: `status: open`, empty `assignee`, every `blocked_by` ticket closed.
- Resolution: a `## Resolution` section appended to the ticket, then `status: closed`.
- Research findings live in `research/<slug>.md`, linked from the ticket.
