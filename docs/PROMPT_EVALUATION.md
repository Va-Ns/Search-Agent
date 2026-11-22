# Prompt evaluation

This document records how the agent's system prompt, and the code around it, were evaluated and improved. It follows the workflow taught in Anthropic Academy's [*Building with the Claude API*: prompt evaluation](https://academy.claude.com/courses/building-with-the-claude-api/prompt-evaluation) lessons, applied by hand to a local model.

## The workflow

The course describes a five-step loop:

| Step (course) | What it means | How it was applied here |
|---|---|---|
| 1. Draft a prompt | Write a baseline prompt | v1: "You are a helpful assistant ... Use web_search for anything recent ... mention the sources you used." |
| 2. Create an eval dataset | Inputs representative of real use | A small set of test questions (below) |
| 3. Feed through the model | Run every input with the prompt | `uv run agent.py` with `qwen3:8b`, recording the full trace |
| 4. Feed through a grader | Judge each output | A **human grader** and a **model grader** (see below) |
| 5. Change the prompt and repeat | Iterate, and compare | Six versions, one commit each |

## Graders

The course names three kinds of graders: code, model and human. This evaluation combined two of them.

| Grader | Who | What it did |
|---|---|---|
| **Human** | the developer | Ran the agent, read the traces, judged whether each answer was usable, and checked claims against primary sources |
| **Model** | Claude (Anthropic), a much larger LLM than the agent's | Read the traces and the code, reproduced searches outside the agent to separate "bad results" from "bad reading", diagnosed the cause of each failure, and fact-checked the final answers claim by claim against web sources |

There was no fixed scoring rubric. Each run was judged as **fail**, **partial** or **pass** based on the questions in the next section.

## Eval dataset

| ID | Input | Why it's in the set |
|---|---|---|
| T1 | "What is qwen" | Answerable from snippets, and the results contained a misleading entry |
| T2a | "What's the latest news in solving the Riemannian hypothesis problem?" | Recent events after the model's training cutoff |
| T2b | "Are there any claims of solving the Riemannian hypothesis?" | A follow-up in the same conversation (does it search again?) |
| T2c | "Has anyone proven the Riemann hypothesis lately?" | The same topic in different words; the headlines exaggerate |

## What was checked in each run

- Was a final answer printed?
- Did the agent search when it should have, with sensible, non-repeated queries?
- Was the answer based on the tool results, or on the model's memory?
- Did every listed source actually appear in the tool results?
- Were the facts correct when checked against primary sources?

## Progress

| Run | Version | Change | Test | Observed | Verdict |
|---|---|---|---|---|---|
| R1 | v1: first agent | baseline | T1 | Searched twice, then printed an empty answer | **fail** (code bug) |
| R2 | v1.1: loop fix | indentation | T1 | Same query twice; dismissed good results because of one junk entry; answered from memory; no sources | **fail** |
| R3 | v2: structured results | numbered results + explicit prompt rules | T1 | One search, five relevant results, grounded answer, five real sources | **pass** |
| R4 | v3: read_page | second tool, 16k context | T2a | Query said "2023"; no answer printed; ended in a traceback | **fail** (code bug) |
| R5 | v4: date + trace fixes | today's date, longer timeout | T2a | Searches failed (hidden by a trace typo); claimed "no credible announcement" from memory; invented sources | **fail** |
| R6 | v4 | (same) | T2b | No search at all; repeated its earlier answer; made up a "Kumar et al. 2018" retraction | **fail** |
| R7 | v4 | (same) | T2c | No search at all; same answer again | **fail** |
| R8 | v5: grounding rules | 4 anti-memory rules | T2c | Found the November 2026 claimed proof; correct dates; real sources; uncertainty stated | **pass** (one partial: it blurred which outlet covered which result) |

### What each failure taught

| Run | Cause | Fix in the next version |
|---|---|---|
| R1 | `for ... else` attached to the wrong loop | Indentation |
| R2 | The 8B model fixated on one irrelevant result | Numbered results; "ignore irrelevant entries", "never repeat a query", "end with Sources" |
| R4 | Indentation regression; the model doesn't know today's date | Indentation; `Today's date is ...` in the prompt |
| R5 | Failed searches hidden by the trace; the model fell back to its 2023 knowledge | Trace fix; "if searches fail, say so", "only list sources from tool results" |
| R6, R7 | Its own earlier answer in the history | "Always search, including follow-up questions" |

## When the agent beat its grader

The most instructive moment came when the evaluation was turned around.

**1. The agent found news the model grader had missed.** Before run R8, Claude told the developer that Anthropic had *not* claimed a proof of the Riemann hypothesis. That was based on the August 2026 zeta-zeros result, which was all Claude's own searches had found. In R8, the local 8B agent then reported Levent Alpöge's Claude-assisted Lean proof, released **November 20, 2026**, three days earlier. Claude's searches had not surfaced that story at all.

**2. The model grader rejected a correct fact.** Claude marked the agent's "17-million-line formalization" as "unverified, probably wrong", because its own (secondary) sources mentioned file counts and bytes but no line count. The developer then pointed to the primary source, the [Lean and Mathlib communities' joint statement](https://leanprover-community.github.io/blog/posts/riemann-hypothesis/) (2026-11-21), which says: *"a Lean library comprising 17 million lines of code."* The agent had been right.

**Final tally on this topic: the agent was correct twice where its far larger grader was wrong.**

What this shows:

- **For recent facts, what decides the outcome is the search results, not the size of the model.** A small model with a good search beat a large one with an incomplete search.
- **A model grader can be wrong.** The course warns that model graders "can be somewhat capricious". Here, the grader made the same mistake it had criticized in the agent: it turned "not found in my sources" into "probably false".
- **The human grader, going to primary sources, settled it.** Combining both graders worked better than either alone. The model grader was fast at diagnosing code and prompt failures, and the human grader caught the grader's own error.

## Limitations

- **One run per version.** Both the search engines and the model are non-deterministic, so the same question can turn out differently on another run.
- **Different test questions per version.** v1-v2 were tested on T1, and v3-v5 on T2. The table shows progress, but not a controlled comparison.
- **Code and prompt changes are mixed.** R1 and R4 failed because of code bugs, not the prompt.
- **A small dataset.** The course notes that real eval sets have tens to thousands of records.

## Next step: an automated eval pipeline

Following the course's structure (`run_prompt` -> `run_test_case` -> `run_eval`), several of the checks above can be graded by code:

| Check | Grader | How |
|---|---|---|
| Answer printed | code | final message non-empty |
| Searched, no repeated queries | code | at least one `web_search` call for recent-event questions; no duplicate queries |
| Sources real | code | every URL under `Sources:` appears in some tool result |
| Grounded and correct | model + human | a grader model returns strengths, weaknesses, reasoning and a score, as in the course; a human spot-checks claims against primary sources |

Running each question several times per prompt version would turn this record into a regression test for future prompt changes.
