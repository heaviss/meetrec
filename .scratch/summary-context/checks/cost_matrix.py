"""THROWAWAY (ticket 04): summary cost and quality by model x effort, agent over the context folder (-> 03).

Needs context_source.py from the prototype branch next to it:
    git show prototype/context-source:.scratch/summary-context/checks/context_source.py > context_source.py

Per meeting: 6 cells (opus/sonnet/haiku x medium/low) plus opus-medium without <glossary>, then one Opus
judge call that scores all 7 blinded summaries against the transcript. Outputs (real speech) go to OUT/.

    uv run python .scratch/summary-context/checks/cost_matrix.py OUT ~/Recordings/2026-11-12-1400 ...
"""

import json
import random
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from context_source import CONTEXT_NOTE, build_context  # noqa: E402

from meetrec.config import PROMPT_FILE, load_config  # noqa: E402
from meetrec.summary import glossary, summary_input, system_prompt  # noqa: E402

MODELS = {"opus": "claude-opus-5-5", "sonnet": "claude-sonnet-5-5", "haiku": "claude-haiku-5-5"}
CELLS = [(m, e, True) for m in MODELS for e in ("medium", "low")] + [("opus", "medium", False)]

JUDGE = """You grade meeting summaries. Input: <glossary> (correct project terms), <transcript> (speech recognition, \
garbled names and terms), and several <summary id="..."> written from it. The user is {user}.
Score each summary 1-5 on:
- facts: no hallucinations, nothing contradicts the transcript
- tasks: action items for the user and others found, with owners
- decisions: decisions and open questions captured
- terms: names, terms and ticket numbers restored correctly (glossary wins over transcript spelling)
- brevity: no padding, readable in a minute
Return only JSON: {{"<id>": {{"facts": n, "tasks": n, "decisions": n, "terms": n, "brevity": n, "note": "<one line: the worst flaw>"}}, ...}}"""


def cell_name(model: str, effort: str, glossed: bool) -> str:
    return f"{model}-{effort}" + ("" if glossed else "-noglossary")


def summarize(meeting: Path, ctx: Path, out: Path, model: str, effort: str, glossed: bool) -> dict:
    cfg = load_config()
    name = cell_name(model, effort, glossed)
    lang = json.loads((meeting / "meta.json").read_text())["language"]
    text = summary_input((meeting / "transcript.md").read_text(), glossary(cfg.glossary_repo) if glossed else "")
    prompt = out / f"{name}-prompt.md"
    prompt.write_text(system_prompt(cfg.user_name, lang) + CONTEXT_NOTE["agent"])
    command = list(cfg.summary_command)
    command[command.index("--tools") + 1] = "Read,Grep,Glob"
    command = [a.replace(PROMPT_FILE, str(prompt)) for a in command]
    command += ["--permission-mode", "dontAsk", "--model", MODELS[model], "--effort", effort, "--output-format", "json"]
    began = time.monotonic()
    reply = subprocess.run(command, input=text, cwd=ctx, capture_output=True, text=True, check=True)
    result = json.loads(reply.stdout)
    (out / f"{name}.md").write_text(result["result"])
    u = result["usage"]
    return {
        "meeting": meeting.name,
        "cell": name,
        "s": round(time.monotonic() - began),
        "usd": round(result["total_cost_usd"], 3),
        "turns": result.get("num_turns"),
        "in": u["input_tokens"] + u.get("cache_read_input_tokens", 0) + u.get("cache_creation_input_tokens", 0),
        "out": u["output_tokens"],
        "stdin_chars": len(text),
    }


def judge(meeting: Path, out: Path) -> dict:
    cfg = load_config()
    names = [cell_name(*c) for c in CELLS]
    blind = dict(zip(random.sample(range(100, 1000), len(names)), names, strict=True))
    (out / "judge-key.json").write_text(json.dumps(blind))
    summaries = "\n\n".join(f'<summary id="{k}">\n{(out / f"{n}.md").read_text()}\n</summary>' for k, n in blind.items())
    text = summary_input((meeting / "transcript.md").read_text(), glossary(cfg.glossary_repo)) + "\n\n" + summaries
    command = ["claude", "-p", "--no-session-persistence", "--tools", "", "--setting-sources", "project",
               "--strict-mcp-config", "--model", MODELS["opus"], "--effort", "high", "--output-format", "json",
               "--system-prompt", JUDGE.format(user=cfg.user_name)]
    result = json.loads(subprocess.run(command, input=text, capture_output=True, text=True, check=True).stdout)
    raw = result["result"]
    scores = json.loads(raw[raw.index("{") : raw.rindex("}") + 1])
    (out / "judge.json").write_text(json.dumps(scores, ensure_ascii=False, indent=1))
    return {"usd": round(result["total_cost_usd"], 3), "scores": {blind[int(k)]: v for k, v in scores.items()}}


def main(out_root: Path, meetings: list[Path]) -> None:
    jobs = []
    for meeting in meetings:
        out = out_root / meeting.name
        ctx = out / "ctx"
        shutil.rmtree(ctx, ignore_errors=True)
        ctx.mkdir(parents=True)
        build_context(meeting, ctx)
        jobs += [(meeting, ctx, out, *cell) for cell in CELLS]
    with ThreadPoolExecutor(6) as pool:
        rows = list(pool.map(lambda job: summarize(*job), jobs))
        verdicts = dict(zip(meetings, pool.map(lambda m: judge(m, out_root / m.name), meetings), strict=True))
    for row in rows:
        verdict = verdicts[next(m for m in meetings if m.name == row["meeting"])]
        marks = verdict["scores"][row["cell"]]
        row["score"] = sum(v for k, v in marks.items() if k != "note")
        row["marks"] = {k: v for k, v in marks.items() if k != "note"}
    (out_root / "stats.json").write_text(json.dumps({"rows": rows, "judge_usd": [v["usd"] for v in verdicts.values()]}, indent=1))
    for row in rows:
        print(row["meeting"], row["cell"], row["s"], row["usd"], row["turns"], row["in"], row["out"], row["score"], sep="\t")


if __name__ == "__main__":
    main(Path(sys.argv[1]), [Path(a) for a in sys.argv[2:]])
