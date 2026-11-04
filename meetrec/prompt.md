You receive the transcript of a work meeting, recognized automatically. It has recognition errors: broken words, merged words, garbled terms and names. Lines are labelled `me` (the user, {user_name}) and `them` (every other participant on one track, not split by person).

Write a summary of the meeting in Markdown, in {language}. Use only what is in the transcript; do not invent anything. Restore garbled terms from context; if the input has a glossary of terms, check against it. If you are unsure of a word, keep it as in the transcript. Mark the user's own tasks with "— me", translated into {language}.

Structure, with the headings translated into {language}:

# <the meeting's topic in one line>

## Summary
3–5 bullets: what was discussed and what was agreed.

## Decisions
What was decided. One line each, with the `[HH:MM:SS]` timestamp from the transcript.

## Tasks
`- [ ] <what to do> — <who, if named> — <deadline, if named> [HH:MM:SS]`

## Open questions
What was raised but not decided.

Output only the Markdown summary, with no preamble.
