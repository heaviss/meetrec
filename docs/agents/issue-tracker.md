# Issue tracker: Local Markdown

Issues, specs and wayfinder maps for this repo live as markdown files in the repo; git is the history. The state of every file sits in its YAML frontmatter.

## Issues

- One feature per directory: `.scratch/<feature-slug>/`
- The spec is `.scratch/<feature-slug>/spec.md`
- Implementation issues are one file per ticket at `.scratch/<feature-slug>/issues/<NN>-<slug>.md`, numbered from `01`, never a single combined tickets file
- Triage state is the frontmatter `status:` field, holding one of the label strings from `triage-labels.md`, or `closed`
- Comments and conversation history append to the bottom of the file under a `## Comments` heading

## When a skill says "publish to the issue tracker"

Create a new file under `.scratch/<feature-slug>/` (creating the directory if needed).

## When a skill says "fetch the relevant ticket"

Read the file at the referenced path. The user will normally pass the path or the issue number directly.

## Wayfinding operations

Used by `/wayfinder`. The **map** is a file with one **child** file per ticket.

- **Where**: the first effort lives in `wayfinder/` (SPEC.md sits beside its tickets and links them); a new effort gets `.scratch/<effort>/`.
- **Map**: `<effort dir>/map.md` (Destination / Notes / Decisions so far / Not yet specified / Out of scope).
- **Child ticket**: `<effort dir>/NN-<slug>.md`, numbered from `01`, the question under `## Question`. Frontmatter:
  ```yaml
  type: research | prototype | grilling | task
  status: open | closed
  assignee:            # empty = unclaimed
  blocked_by: [NN, NN]
  ```
- **Blocking**: `blocked_by` lists ticket numbers; a ticket is unblocked when every listed ticket is `closed`.
- **Frontier**: tickets with `status: open`, an empty `assignee` and no open blocker; first by number wins.
- **Claim**: set `assignee: claude` (or the driving dev) and commit before any work.
- **Resolve**: append the answer under `## Resolution`, set `status: closed`, then append a context pointer (gist + link) to the map's Decisions so far.
- **Research findings**: `<effort dir>/research/<slug>.md`, linked from the ticket. Throwaway scripts for a `task` ticket: `<effort dir>/checks/`. Prototypes go on a `prototype/<name>` branch, never into `master`.
