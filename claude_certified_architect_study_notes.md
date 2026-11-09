# Claude Certified Architect – Foundations: Study Notes

Study notes built from the 23-video *Claude Certified Architect – Full Course* playlist by Peace Of Code. The notes follow the five exam domains, not the episode order, so related ideas sit together. Each section has:

- **Core concepts**: what the idea is and why it exists
- **Rules to remember**: the decision rules the exam checks
- **Exam signals & traps**: wording that points to the right answer, and the distractors to drop
- **Scenario drills**: practice questions with collapsible answers

> Source episodes are tagged like `[Ep 05]`, using the course's own numbering. Where the course simplifies or may be out of date, a **⚠ Verify** note says what to check in the official exam guide or the Anthropic docs.

---

## Contents

0. [Exam Overview & Strategy](#0-exam-overview--strategy)
1. [Domain 1 – Agentic Architecture & Orchestration (~27%)](#domain-1--agentic-architecture--orchestration-27)
2. [Domain 2 – Tool Design & MCP Integration (~18%)](#domain-2--tool-design--mcp-integration-18)
3. [Domain 3 – Claude Code Configuration & Workflows (~20%)](#domain-3--claude-code-configuration--workflows-20)
4. [Domain 4 – Prompt Engineering & Structured Output (~20%)](#domain-4--prompt-engineering--structured-output-20)
5. [Domain 5 – Context Management & Reliability (~15%)](#domain-5--context-management--reliability-15)
6. [Mixed Practice Exam (20 questions)](#6-mixed-practice-exam)
7. [One-Page Cheat Sheet](#7-one-page-cheat-sheet)

---

## 0. Exam Overview & Strategy

### Format `[Ep 00, Bonus, 2026 Update]`
| Item | Detail |
|---|---|
| Length | 120 minutes, proctored |
| Scoring | Scaled score out of 1,000; **720 to pass**; valid for 12 months |
| Question style | Scenario-based. Most are single-answer multiple choice, but **some are multiple-response** ("select two") |
| Eligibility | Through the **Claude Partner Network**. You register with a company-domain email; Gmail and other personal addresses don't work |
| Results | About 2 days after the exam |

### The six exam scenarios
Every question sits in one of these settings. The course builds or discusses each of them:
1. **Customer support agent**: tools `get_customer`, `lookup_order`, `process_refund`, `escalate_to_human`
2. **Code generation with Claude Code**
3. **Multi-agent research system**: coordinator plus search, analysis and synthesis sub-agents
4. **Developer productivity**: built-in tools for exploring a codebase
5. **Claude Code in CI/CD**
6. **Structured data extraction**: invoices, medical records, contracts

### Domain weighting and study priority
| Domain | Weight | Priority |
|---|---|---|
| D1 Agentic architecture & orchestration | ~27% | 1st |
| D3 Claude Code configuration & workflows | ~20% | 2nd |
| D4 Prompt engineering & structured output | ~20% | 2nd |
| D2 Tool design & MCP integration | ~18% | 3rd |
| D5 Context management & reliability | ~15% | 4th |

D1 + D3 + D4 ≈ **67%** of the exam.

### The four distractor traps `[Bonus]`
These four patterns explain most wrong answers on the exam:

| Trap | What it looks like | Why it's wrong |
|---|---|---|
| **1. Prompt-only fix for a "must/never" rule** | "Add stronger wording", "add few-shot examples" when the scenario needs a guarantee | Prompts are probabilistic. A guarantee needs **code** (a hook or gate) |
| **2. Over-engineered "first step"** | A full rebuild offered when the question asks for the *most effective first step* | The right first step is usually the cheapest targeted fix |
| **3. Premature infrastructure** | New classifier, routing layer, microservice or sub-agent | Optimize what exists first: tool descriptions, tool scoping, config |
| **4. Sentiment or confidence as a signal** | "Escalate when confidence < 70%", "escalate when the customer is angry" | Self-reported confidence isn't calibrated, and sentiment doesn't mean a human is needed |

> **One-line filter:** when two answers both seem plausible, ask whether the option **guarantees** the outcome or only makes it **more likely**. If the question says *must*, *never* or *guarantee*, pick the guarantee.

### Exam-day playbook
- Read each scenario twice and find the **pain point**: the symptom, then the root cause, then the fix.
- "Most effective first step" means the cheapest fix that targets the root cause, not the most complete solution.
- Be suspicious of **made-up specifics**: flags, environment variables or parameters that sound official but don't exist, such as `--headless`, `CLAUDE_HEADLESS=true` or `--batch`.
- If you're stuck, flag the question and move on.

---

## Domain 1 – Agentic Architecture & Orchestration (~27%)

### 1.1 Message roles `[Ep 01]`
Every message in a Claude API conversation has a role:
- **system**: who the model is and how it should behave. Set once, for example "You are a support agent for…"
- **user**: input coming into Claude. This includes the end user's messages **and tool results your code sends back**.
- **assistant**: Claude's own output, including its `tool_use` requests.

**Why it matters:** the Claude API is **stateless**. Each call has to include the **full conversation history** with the right roles, or Claude has no context.

### 1.2 The agentic loop and `stop_reason` `[Ep 01]`
A chat interaction is one request and one response. An **agent** runs a loop instead: reason → act (call a tool) → observe the result → reason again, until the task is done.

**Loop lifecycle:**
1. Send `messages[]` plus the list of `tools` to the API.
2. Read **`stop_reason`** on the response:
   - **`tool_use`**: Claude wants to call one or more tools. Append the **assistant message (which contains the `tool_use` blocks) first**. Run each tool **in your own code**, then append the results as a **user** message with `tool_result` blocks whose **`tool_use_id` matches** the request. Loop again.
   - **`end_turn`**: Claude is finished. Pull out the final text and **exit the loop**.
3. Keep an iteration cap (for example 50) **only as a safety valve**.

**Key facts**
- Claude never runs tools itself. It **asks** for a tool call, and your code runs it and returns the result.
- The **model chooses which tool to use**, based on the tool descriptions. That's what makes it agentic rather than a fixed script.
- `end_turn` is the **only valid primary exit** from the loop.
- Order of appends: **the assistant message first, then the user message with the tool results**.

**The three loop anti-patterns (tested)**
| Anti-pattern | Why it fails |
|---|---|
| **Parsing Claude's text** to decide when to stop ("if 'done' in text") | The wording changes from run to run, and a `tool_use` turn may have **no text block at all**, which can crash an index lookup |
| **Iteration cap as the main stop condition** | The cap is a backstop, not the logic that ends the loop |
| **Checking content type instead of `stop_reason`** | Content type and `stop_reason` measure different things |

### 1.3 Multi-agent systems: hub-and-spoke `[Ep 02]`
**Why a single agent fails:**
- **Context overflow**: tool results pile up until the context window is full before the task ends.
- **Sequential bottleneck**: independent subtasks wait in line.
- **Specialization gap**: one agent doing everything gives generic results.

**Hub-and-spoke topology:**
- A **coordinator** sits in the middle. **All communication goes through it.**
- Sub-agents don't know about each other and **never talk to each other directly**. This keeps them independent, lets them run in parallel, and keeps everything observable.

**The coordinator's four responsibilities:**
1. **Task decomposition**: break the request into scoped pieces.
2. **Delegation**: spawn the right specialist sub-agent for each piece.
3. **Result aggregation**: combine the outputs into one result.
4. **Error handling**: deal with sub-agent failures gracefully.

### 1.4 The Task tool and AgentDefinition `[Ep 02, 04]`
- A coordinator spawns sub-agents through the **Task tool**. In the Agent SDK, **`Task` must be in the coordinator's `allowedTools`**; without it the coordinator can't delegate.
- The Task call carries an **AgentDefinition** with four fields:

| Field | Purpose |
|---|---|
| `description` | The sub-agent's role or label, for example "web search specialist" |
| `prompt` | Its instructions, goal and **all the context it needs** |
| `allowedTools` | The limited set of tools this worker may use |
| `model` | Which model it runs on |

- **Permission matrix:** ordinary worker sub-agents **should not** have the Task tool, because workers spawning workers breaks hub-and-spoke. The exception is a **hierarchical sub-coordinator** that is deliberately designed to delegate one level further down.
- The Task tool belongs to Claude Code and the Agent SDK. With the raw Anthropic Python SDK you write the orchestration yourself in normal functions. That's fine for learning, but the exam tests the concepts and patterns. `[Ep 04]`

> ⚠ **Verify:** recent Agent SDK versions may name the sub-agent tool differently, for example `Agent`. Check the current docs. The concept being tested doesn't change.

### 1.5 Parallel vs sequential spawning `[Ep 02, Bonus]`
- **Parallel spawning means emitting several Task tool calls in ONE coordinator response.**
  - Total time ≈ **max(S1, S2, S3)**
- Spawning one sub-agent per turn and waiting for each is **sequential**.
  - Total time ≈ **S1 + S2 + S3**
- **Exam diagnostic:** if a multi-agent system is about 3× slower than expected, the coordinator is making the **sequential anti-pattern**.

### 1.6 Context isolation and context passing `[Ep 02, 03]`
- **Sub-agents start with a blank context.** They **do not** inherit the coordinator's conversation history. All they know is what's in the Task `prompt`.
- So the **coordinator must inject the context explicitly** into the sub-agent's prompt.
- **Exam rule:** if a sub-agent gives irrelevant, duplicated or context-unaware output, the root cause is almost always **missing explicit context injection**.

**Good vs bad sub-agent prompts**
- ❌ "Here are the findings from the previous agents, synthesize them." The sub-agent can't see any "findings".
- ❌ Rigid step-by-step instructions such as "go to Google Scholar, then…". They break as soon as reality differs.
- ✅ State the **goal**, the **context and data it needs**, and the **constraints or quality criteria**.

**Structured context passing (the finding object pattern)**
Pass **structured data**, not prose summaries. Each finding is an object with the claim, source URL, title, page, retrieval date and confidence. Serialize it into the prompt and add requirements such as "cite a source for every claim" or "flag conflicts".

### 1.7 Attribution: claim-source mappings `[Ep 03, 20]`
- **Problem:** when ten search results get summarized into a paragraph, **every link to the original sources is lost**.
- **Fix: claim-source mappings.** Each claim carries a `source_id` that points to a sources list. **Pass the whole object to the next agent**; never pass only the claims.
- **Conflicting sources:** don't silently pick one. Add a **conflict object** that annotates **both** claims with their sources, mark it **unresolved**, and **send it to the coordinator** (or a human) to decide.
- **Never let a sub-agent resolve a source conflict on its own.**

### 1.8 Task decomposition strategies `[Ep 05]`
Ask yourself: **do I know the steps before I start?**

| | Prompt chaining | Dynamic decomposition |
|---|---|---|
| Steps | Fixed and known up front, run in order | Each step comes from what the previous one found |
| Control | High, reproducible | Lower, adaptive |
| Best for | Code review pipelines, compliance, CI/CD | Bug investigation, incident response, open-ended research |
| Example | Review each file → find cross-file issues → write the PR summary | "Start with the last 24 hours of error logs, decide the next step based on what you find, continue until you reach a root cause" |

⚠ **Don't use prompt chaining for open-ended tasks.** Steps fixed in advance go wrong once the real findings move away from your assumptions.

**Narrow decomposition trap `[Bonus, official Q7]`:** the coordinator splits "EV battery landscape" into chemistry, market share and pricing. The final report leaves out regulation and supply chain, even though the source documents covered both. **Root cause: the coordinator's decomposition was too narrow**, not context limits and not sub-agents failing to talk to each other.

### 1.9 Session management `[Ep 03]`
Claude Code offers three ways to keep or restart context:

| Pattern | Command | Use when |
|---|---|---|
| **Named resume** | `claude --resume <session-name>`, or plain `claude --resume` for the most recent session | You're continuing the **same sequential task** and the earlier context is **still valid** |
| **Fork session** | Fork from an existing baseline session | You want to **explore two or more approaches in parallel** from a shared baseline without disturbing it, like Git branches |
| **Fresh start + injected summary** | New session, with a summary of earlier findings pasted in | The earlier tool results are **stale**, for example after a big refactor, or a long context is hurting reasoning |

**Rules**
- **When you resume, always say what has changed** since last time: which files, dependencies or requirements. The agent can't detect changes by itself.
- When you inject earlier findings into a fresh session, present them as **hypotheses to check, not established facts**.
- Use fork **only for parallel exploration**, not for targeted file updates.
- Decision flow:
  1. Are the existing results fundamentally stale? → **fresh session + hypotheses**
  2. Otherwise, are you comparing parallel approaches? → **fork**
  3. Otherwise → **`--resume` and list the changed files**

> ⚠ **Verify:** the exact flags for starting a named session and for forking (for example `--fork-session`). The course is unsure about the exact syntax. The exam is more likely to test *which pattern* fits than the flag spelling.

### 1.10 Hooks: deterministic enforcement `[Ep 05]`
**Prompts are probabilistic; hooks are deterministic.** A system-prompt rule like "never refund over $500" is a *request*, and it still fails sometimes. When the scenario says **guarantee / must never / policy requires**, the answer is **enforcement in code: a hook**.

| Hook | Runs | Use for |
|---|---|---|
| **PreToolUse** | **Before** a tool runs. It can **block**, change or allow the call | **Policy enforcement**, such as refund > $500 → block and escalate; **prerequisite gates** |
| **PostToolUse** | **After** a tool returns, **before the model sees the result** | **Data normalization**: status codes 3/5 → "shipped"/"refunded", epoch → readable date; **trimming large outputs**; setting session flags |

- A hook should only act on the tools it cares about and **pass everything else through** unchanged.
- **Prerequisite gate:** a PreToolUse hook that tracks session state and blocks downstream tools (`process_refund`, `lookup_order`) **until an upstream tool (`get_customer`) has succeeded and set a `verified` flag**. A PostToolUse hook sets that flag after `get_customer` returns `found`.
- **Structured handoff summary:** when you escalate to a human or another agent, send a **self-contained summary** with customer and order details, what was tried, why it was escalated, priority and routing tier. A bare "please assist" forces the receiver to re-read the whole transcript.

### 1.11 Hands-on capstone: what it showed `[Ep 04]`
- The coordinator breaks the request down → a **verification sub-agent** confirms the customer exists → its **structured finding** goes to a **refund sub-agent**, which looks up the order and processes the refund → the coordinator combines the results.
- Each sub-agent runs **its own agentic loop**.
- When verification fails (customer C99 doesn't exist), the pipeline stops cleanly. Without structured context passing, the second agent might have run anyway and invented results.

### Domain 1: exam signals
- "**Guarantee** that X is called before Y" → **PreToolUse prerequisite gate**
- "System is 3× slower than expected" → **sequential spawning; emit all Task calls in one response**
- "Sub-agent output is generic or duplicated" → **missing context injection in the Task prompt**
- "Attribution lost" → **claim-source mappings (structured objects)**
- "Two sources conflict" → **annotate both, mark unresolved, send to the coordinator**
- "Report misses whole topics" → **coordinator's decomposition was too narrow**
- "Know the steps up front" → **prompt chaining**; "investigate an unknown" → **dynamic decomposition**

### Domain 1: scenario drills

**Q1.** A support agent sometimes calls `process_refund` before `get_customer` has returned a verified ID, even though the system prompt says to always verify first. What is the most reliable way to guarantee the correct order?
A) Stronger wording in the system prompt B) Few-shot examples showing the order C) A PreToolUse prerequisite gate that blocks `process_refund` until verification succeeds D) `tool_choice: any`
<details><summary>Answer</summary>

**C.** "Guarantee" calls for code enforcement. A and B are probabilistic prompt fixes. D only forces *some* tool call; it doesn't control the order.
</details>

**Q2.** An agent loop ends when the assistant text contains "task complete". In production it sometimes crashes with an index error, and sometimes it exits early. What's wrong?
<details><summary>Answer</summary>

It's parsing natural language to control the loop. Wording varies, and `tool_use` turns may have no text block. **Exit only on `stop_reason == "end_turn"`**, keep the iteration cap only as a safety valve, and keep looping while `stop_reason == "tool_use"`.
</details>

**Q3.** A coordinator calls the Task tool, waits for the result, then calls it again for the second sub-agent, then the third. The three subtopics are independent. What's the fix?
<details><summary>Answer</summary>

Emit **all three Task tool calls in a single coordinator response** so they run in parallel. Total latency becomes the maximum of the three instead of the sum.
</details>

**Q4.** A synthesis sub-agent writes a generic report that ignores the research findings. Its Task prompt says "Synthesize the findings from the previous agents into a report." Root cause?
<details><summary>Answer</summary>

**Sub-agents don't inherit the coordinator's context.** The findings were never injected. The coordinator must put the structured findings (claims with sources) directly into the Task `prompt`.
</details>

**Q5.** Your codebase analysis session ran 3 days ago; since then only the payments module was refactored. Resume, fork or start fresh?
<details><summary>Answer</summary>

**`--resume`** and tell the agent exactly which files changed so it re-analyzes only those. If the analysis were a month old with most modules rewritten, you'd **start fresh** and inject the old findings as hypotheses to check.
</details>

**Q6.** You want to compare two refactoring strategies starting from the same long-running baseline analysis. Which session pattern?
<details><summary>Answer</summary>

**Fork the session.** Both forks start from the same baseline, explore separately, and leave the baseline untouched.
</details>

**Q7.** A refund tool returns `status: 3` and `created: 1716940800`, and the agent shows these raw values to users. Where does the fix go?
<details><summary>Answer</summary>

A **PostToolUse hook** that converts status codes to labels and epochs to dates **before the model sees the result**.
</details>

---

## Domain 2 – Tool Design & MCP Integration (~18%)

### 2.1 Tool descriptions drive tool selection `[Ep 06]`
- Claude picks a tool **only by reading its name and description**. There's no separate routing layer. Descriptions are written **for the model**, not for developers.
- **A production-grade description covers:**
  1. **What** the tool does
  2. **When** to call it, including prerequisites and order (for example "always call `get_customer` first")
  3. **When not** to use it, and its boundaries
  4. **What** it returns, plus its input format
- **Cross-referencing:** descriptions can name other tools, for example "only call after `get_customer` and `lookup_order` have both succeeded".

### 2.2 Description overlap and misrouting `[Ep 06]`
- **Problem:** `search_web` "search for information", `search_documents` "search documents for information" and `analyze_content` "analyze and extract information" all look like synonyms to Claude, so it misroutes.
- **Fix:** make the descriptions **mutually exclusive**:
  - **web search** = the live internet, for recent events and URLs **not already in the corpus**
  - **document search** = the **already-loaded** corpus
  - **analyze** = processing **after content has been retrieved**
- **Naming:** avoid generic names like `search`, `get_data`, `process` or `handle_request`. Use specific names such as `search_live_web`, `lookup_customer_profile` or `retrieve_order_history`. Split broad tools the way you'd design DAO or repository methods: `get_customer_by_id`, `list_customer_orders`.

**Exam rule:** if the wrong tool is chosen, a tool is never called, or cases are escalated when they shouldn't be, **fix the tool descriptions and names first.** That comes before few-shot examples, classifiers or new sub-agents. (This is official sample question 2.)

### 2.3 System prompt and tool alignment `[Ep 06]`
- A narrow role such as "You are a customer **lookup** assistant" **pushes** Claude toward lookup tools and away from `process_refund`.
- Align the system prompt with the tools: state the **goal** (resolve returns and refunds) and the **tool sequence**: `get_customer` → `lookup_order` → `process_refund` if eligible → `escalate_to_human` **only as a last resort**.

### 2.4 Structured error handling in tools `[Ep 07]`
- **The silent killer:** a tool fails, returns an empty array or a vague message, and the model **treats it as success**, carrying on confidently with bad data.
- **Fix:** return the result with **`isError: true`** (MCP) **plus structured metadata**, so the model **knows** something failed and can reason about recovery.

**Four error categories**
| Category | Example | Retryable? |
|---|---|---|
| **Transient** | Timeout, network blip, service briefly down | **Yes**. Retry, possibly after a delay |
| **Validation** | Malformed or invalid input | **Not with the same input**. Fix the input, then retrying with corrected values can work |
| **Business logic / policy** | Refund > $500 | **No**. Route differently, for example escalate |
| **Permission** | Agent not allowed to use the tool or resource | **No** |

**Good error payload:** `isError: true`, `errorCategory`, `isRetryable`, a human-readable description, `retry_after_ms` (only when retryable), and `alternatives` (fallback tools or sources).

**Local recovery before escalation**
1. The tool fails.
2. The sub-agent **retries transient errors locally** once or twice.
3. Only when local options are used up does it **escalate a structured error to the coordinator**, which then retries, reroutes, picks another sub-agent or escalates to a human.

- ❌ **Ending the whole pipeline on one failure** is an all-or-nothing anti-pattern.
- ❌ **Returning an empty array on failure** hides the error.

### 2.5 Tool overload and scoped tool access `[Ep 07, 08]`
- **More tools ≠ a better agent.** A large tool set **lowers selection reliability** and causes hard-to-debug misfires.
- **Scoped tool access / least privilege:** each agent only sees the tools for its role.
  - coordinator → `get_customer`, `escalate`
  - order agent → `lookup_order`, `process_refund`
  - comms agent → `send_email`, `create_ticket`
- **Synthesis agent drill `[Ep 07, Bonus]`:** if a synthesis agent starts running fresh web searches mid-synthesis, **scope it down to the one tool it needs (`verify_fact`)**. Better descriptions won't fix this: it understands the web search tool, it just shouldn't have access to it.
- The course says all of an agent's tools are loaded into context at once, so a bloated tool list pollutes context. That's another reason to scope.

> ⚠ **Verify:** newer Claude Code versions can defer or search tools instead of loading every schema up front. For the exam, the principle stays the same: **scope tools to the role**.

### 2.6 `tool_choice` `[Ep 07, 16]`
| Value | Behavior | Use for |
|---|---|---|
| `{"type": "auto"}` | Model decides; may call a tool or just reply with text | Conversational agents |
| `{"type": "any"}` | **Must call at least one tool**; the model picks which | **Guaranteed structured output** when several extraction tools exist |
| `{"type": "tool", "name": "X"}` | **Must call exactly tool X** | Single-schema extraction; tightest control |

- **Exam signal:** "guarantee structured output / a tool call every time" → **`any`**, or **forced `tool`** for one specific schema.
- `any` doesn't fix *which* tool gets picked. Good descriptions still matter.

> ⚠ **Verify:** the API also supports `{"type": "none"}`, which the course doesn't cover.

### 2.7 MCP (Model Context Protocol) fundamentals `[Ep 08]`
- MCP is an **open protocol, created by Anthropic**, that standardizes how AI apps **discover and use** external tools, **resources** and **prompts**. It's often called "USB-C for AI". Tools become reusable across agents and apps instead of being hard-coded into one agent.
- **Architecture:** a **host** (the agent or app) contains an **MCP client**, which talks to an **MCP server** that exposes tools, resources and prompts.
- **Wire format:** **JSON-RPC 2.0**.
  - **Transports:** **stdio** for local servers, run as a subprocess; **Streamable HTTP** (or SSE) for remote servers.
- **Lifecycle:**
  1. **connect**
  2. **initialize** (negotiate capabilities; MCP sessions are **stateful**)
  3. **discover** (`tools/list`)
  4. **reason**
  5. **invoke** (`tools/call`)
  6. **structured result**
- **MCP doesn't replace APIs.** APIs serve apps and microservices; MCP wraps capabilities so **AI** can discover them. If a backend API contract changes, you update the MCP server and the agent keeps working.
- **Security:** MCP doesn't add authentication or authorization. Keep OAuth and tokens in place, trust only known servers, and watch for **prompt injection and tool poisoning**.
- **Testing:** **MCP Inspector**, Anthropic's tool for connecting to a server, listing tools and calling them.

### 2.8 MCP configuration: `.mcp.json` vs `~/.claude.json` `[Ep 08]`
| File | Location | Scope | Contents |
|---|---|---|---|
| **`.mcp.json`** | **Project root**, committed to Git | **Shared with the team and CI** | The MCP servers **the project** needs |
| **`~/.claude.json`** | **Home directory**, never shared | **Just you** | Personal servers and personal settings |

- **Classic exam bug:** "It works on my machine, but teammates don't get the MCP tools after pulling." → The servers were set up in **`~/.claude.json`**. **Move them to `.mcp.json` at the project root and commit it.**
- **`.mcp.json` structure:** a top-level `mcpServers` object, with one entry per named server:
  - **stdio:** `command` + `args` (for example `npx …`). Claude starts it as a **local subprocess**.
  - **remote:** `url` (HTTP/SSE). Claude connects as a **client**.
  - The type you choose depends on **where the server runs**, not what it does.
- **Secrets:** never hard-code them. Use **environment variable expansion**, for example `"GITHUB_TOKEN": "${GITHUB_TOKEN}"`. The value comes from the shell or container environment **at runtime**: the variable *name* is committed, the *value* stays local.

### 2.9 MCP resources, and community vs custom servers `[Ep 08]`
- **Resources:** content a server exposes directly, such as docs, schemas or templates, as a **catalog Claude sees up front**. That avoids five exploratory tool calls when **one** lookup would do.
  - **Exam framing:** use resources so Claude doesn't burn tokens on discovery.
- **Community servers** (GitHub, filesystem, fetch and so on) cover standard needs. Start with these and **improve their tool descriptions through overrides in `.mcp.json`**.
- **Custom servers** (built with something like FastMCP) are for **internal or proprietary** systems, kept on your network with authentication.
- **Built-in tools compete with MCP tools:** if an MCP tool's description is vague, Claude falls back to its native `Grep` and friends. **A rich description, saying when to use this tool instead of grep, is the highest-leverage fix.**

### Domain 2: exam signals
- "Wrong tool picked / single-sentence descriptions" → **expand tool descriptions** (what, when, when not, returns)
- "Synonym-like tools" → **mutually exclusive descriptions, specific names**
- "Model treats a failure as success" → **`isError` + structured error metadata**
- "Can we retry?" → transient **yes**; validation **only after fixing the input**; business/permission **no**
- "Terminate the pipeline on error" → **anti-pattern**
- "Agent has 20 tools and misfires" → **scoped tool access**
- "Guaranteed structured output" → **`tool_choice: any`** or a forced tool
- "Teammates don't see the MCP tools" → **`.mcp.json` in the project root**
- "Credentials committed" → **`${ENV_VAR}` expansion**
- "Agent uses grep instead of the MCP search tool" → **improve the MCP tool's description**

### Domain 2: scenario drills

**Q8.** A support agent often calls `escalate_to_human` for cases it could resolve itself, and sometimes calls `process_refund` before verifying identity. All four tools have one-sentence descriptions. What's the most effective first step?
A) Add a tool-routing classifier B) Add 4–6 few-shot examples C) Expand the tool descriptions with input formats, triggering conditions, prerequisites and when-not-to-use boundaries D) Split into four sub-agents
<details><summary>Answer</summary>

**C.** The question points straight at the root cause: thin descriptions. A and D are premature infrastructure. B is a weaker fix that only works after the descriptions are right.
</details>

**Q9.** A sub-agent's database lookup times out. It returns `{"status": "ok", "results": []}`. The coordinator reports "no records found." What went wrong, and what should the sub-agent return?
<details><summary>Answer</summary>

**Silent suppression:** a failure was reported as a valid empty result. It should return `isError: true`, `errorCategory: "transient"`, `isRetryable: true`, a description and alternatives, after first trying a local retry.
</details>

**Q10.** A refund over $500 is blocked by a PreToolUse hook. What error category and retryability should the structured response report?
<details><summary>Answer</summary>

**Business logic / policy violation, `isRetryable: false`.** Route it to escalation; don't retry.
</details>

**Q11.** You commit `.mcp.json` with `"DB_PASSWORD": "hunter2"`. What's the right pattern?
<details><summary>Answer</summary>

`"DB_PASSWORD": "${DB_PASSWORD}"`. The value is filled in from the environment at runtime, so the variable name is committed and the secret stays local.
</details>

**Q12.** An MCP docs server has 500 articles. Claude spends many tool calls searching before it finds the right one. What design change cuts that cost?
<details><summary>Answer</summary>

Expose the articles as **MCP resources**, a catalog Claude can see up front, so it can go straight to the right content instead of searching repeatedly.
</details>

---

## Domain 3 – Claude Code Configuration & Workflows (~20%)

> Claude Code configuration is about **20% of the Architect exam** but only about **3% of the Developer exam** `[2026 Update]`. Expect a lot of questions here.

### 3.1 Built-in tools `[Ep 09]`
| Tool | Job | Notes |
|---|---|---|
| **Grep** | Searches **file contents** | "Every file that imports React", "all calls to `process_refund`", "all TODO comments" |
| **Glob** | Matches **file paths and names by pattern** | "All `.ts` files in `src/`", "every test file", "everything under `terraform/`". **Doesn't look inside files** |
| **Read** | Loads **one whole file** into context | Use once you know which file you need. **Expensive if used in bulk** |
| **Write** | **Creates** a file or **overwrites it completely** | New files, or changes so large that a rewrite is cleaner. Destructive |
| **Edit** | Targeted **find-and-replace** inside a file | **`old_string` must be unique** in the file |
| **Bash** | Shell commands: run tests, install packages, git, CLIs | Use the dedicated Grep tool rather than grep via Bash |

**When Edit fails** because the anchor text isn't unique: **fall back to Read + Write**. Read the whole file, make the change, write the whole file back. It's less elegant but always works.
- **Tip:** a longer, more specific `old_string` makes Edit more likely to succeed.

**Incremental exploration beats bulk reading:**
1. **Grep** for the entry point.
2. **Read** that file.
3. Trace the call chain and grep for the next dependency.
4. Repeat.

Each grep tells you what to read next, and each read tells you what to grep for next.
- ❌ "Read every file first" burns the context window before any reasoning happens. **If an answer says "read all files first," it's almost certainly wrong.**

**Developer productivity workflow:**
1. **Discover:** Glob to map the structure.
2. **Understand:** Grep to locate code, Read to load it.
3. **Create:** Write for new boilerplate files, Edit for surgical fixes.

### 3.2 CLAUDE.md hierarchy `[Ep 10]`
CLAUDE.md is **persistent context** that Claude Code loads at the start of a session, like a briefing document for a new team member.

| Level | Location | Who sees it | Use for |
|---|---|---|---|
| **User** | `~/.claude/CLAUDE.md` | **Only you, never shared**; applies to all your projects | Personal preferences, such as commit message style |
| **Project** | `./CLAUDE.md` or `./.claude/CLAUDE.md` (committed) | **The whole team and CI** | Stack, conventions, architecture, testing rules |
| **Directory** | `<subdir>/CLAUDE.md` | Loaded when working **in that directory and below** | Area-specific guidance, such as Terraform or React conventions |

- **Classic team bug:** a new engineer's Claude knows nothing about the project's conventions. → The original developer put the content in **user-level** `~/.claude/CLAUDE.md`. **Move it to the project level and commit it.**
- **`@import`:** keeps CLAUDE.md **modular**. Split it into focused files (API patterns, testing conventions) and import them. This gives cleaner ownership and fewer merge conflicts. It doesn't make loading conditional.
- **`/memory`:** a **diagnostic command** that shows exactly which memory and config files are loaded in the current session. It's the answer to "how do I check whether Claude is loading my CLAUDE.md or rules?"

### 3.3 `.claude/rules/` and path-scoped rules `[Ep 10, Bonus Q6]`
- Rule files on specific topics live in **`.claude/rules/`**, with **YAML frontmatter**.
- Add a **`paths`** field with glob patterns and the rule becomes **conditional**: it loads only when Claude is working on matching files.
- **CLAUDE.md can't target file patterns; rules with `paths` can.**

```yaml
---
description: TypeScript strict-mode conventions
paths:
  - "src/**/*.ts"
  - "**/*.test.tsx"
---
- Never use `any`; use `unknown` with type narrowing
- Annotate all parameters and return types explicitly
```

**Glob pattern reminder**
- `**` matches any number of directories.
- `*` matches anything within one level.
- `terraform/**/*` matches every file under `terraform/`, at any depth.
- `**/*.test.tsx` matches any `.test.tsx` file anywhere.
- `src/api/*.ts` matches `.ts` files directly in `src/api/` only.

**Exam rule:** "different conventions for different file types or paths, without cluttering CLAUDE.md" → **`.claude/rules/` with `paths` frontmatter**. Not directory CLAUDE.md files, and not `@import`.

### 3.4 Custom slash commands `[Ep 00, 11]`
- A command is a **Markdown file containing a reusable prompt**, run as `/name`. It's static: the same instructions every time.

| Scope | Location | Who gets it |
|---|---|---|
| **Project** | `.claude/commands/` (committed) | **Everyone who clones or pulls the repo** |
| **User** | `~/.claude/commands/` | Just you, across all your projects |

- **Exam keywords:** "available to every developer / all contributors / when they clone" → **`.claude/commands/` in the project repo.** This is also official sample question 1.
- **CLAUDE.md vs commands:** CLAUDE.md holds **standing rules that are always loaded**. Commands are **run on demand**.

### 3.5 Skills `[Ep 11]`
- A skill is more like a **configurable mini-agent** than a macro. It lives in **`.claude/skills/<skill-name>/SKILL.md`**, can bundle templates and reference files, and can be **invoked automatically** when Claude sees that the task matches, or run explicitly.
- **SKILL.md frontmatter:**

| Field | Purpose |
|---|---|
| `name` | Skill identifier |
| `context: fork` | Runs the skill in a **separate sub-agent context** so its intermediate work doesn't flood the main session. Only the final result comes back |
| `allowed-tools` | **Restricts** which tools the skill may use (least privilege) |
| `argument-hint` | Prompts the user for a required argument, such as a file path, if it's missing |

- **Don't mix these up:** **fork isolates execution**; **allowed-tools restricts capability.**
- **Exam scenario:** "A skill analyzes hundreds of files and its intermediate output floods the main conversation." → **`context: fork`**.

**Where things belong**
| Mechanism | Loaded | Isolation | Best for |
|---|---|---|---|
| CLAUDE.md | Always (ambient) | No | Standing project rules, architecture guidance |
| Slash command | On demand (`/name`) | No | Static reusable prompts |
| Skill | On demand, can be auto-invoked | **Yes, with `context: fork`** | Complex multi-step procedures |

> Putting a 50-step procedural checklist in CLAUDE.md clutters every session. Make it a **skill**.

### 3.6 Plan mode vs direct execution `[Ep 12]`
| | Direct execution (default) | Plan mode |
|---|---|---|
| When | The outcome is known and the scope is clear; a mistake is cheap to fix | **Large-scale or architectural change**, several valid approaches, **hard to reverse**, touches many files non-trivially |
| Examples | Fix a bug with a clear stack trace, write tests for one class, update config, generate boilerplate | Monolith → microservices, a refactor across hundreds of files, re-architecting auth, starting a new app |
| Behavior | Acts right away | Reads broadly, maps dependencies, weighs approaches, **presents a plan for approval**, then executes |

- They're **sequential partners, not rivals**: plan first, then execute directly against the approved plan.
- **Exam answer for migrations:** "Use plan mode to produce a phased strategy before making any changes."

### 3.7 Explore sub-agent `[Ep 12]`
- Exploring a large codebase in the main session **fills the context window** with file contents before any reasoning happens.
- **The Explore sub-agent** reads widely in its own context and returns a **compact summary** to the main session.
- **Exam rule:** "context window exhaustion during codebase discovery" → **Explore sub-agent**.

### 3.8 Iterative refinement and the interview pattern `[Ep 12]`
- **Feedback loop:** give **specific** feedback, such as "the catch block on line 42 should log the full error object". "Make it better" gives Claude nothing to work with.
- **Test-driven iteration:** give Claude the tests first, let it generate code, run the tests and feed failures back. Clear pass/fail criteria leave no ambiguity.
- **Concrete examples:** one before/after snippet does more than a page of description.
- **Interview pattern:** ask Claude to **ask you clarifying questions before it starts**. It's the go-to answer for **ambiguous or open-ended requirements** where you want **less rework and a better first attempt**, and you can use it inside plan mode.

**Quick map:** large or irreversible change → plan mode · clear single-file fix → direct execution · context filling during discovery → Explore sub-agent · vague requirements → interview pattern · transformation tasks → concrete examples.

### 3.9 Claude Code in CI/CD `[Ep 13]`
- **Why CI jobs hang:** in interactive mode Claude may stop to ask a clarifying question, and in CI nobody answers, so the job times out.
- **Fix:** run Claude Code **non-interactively with `-p` / `--print`**. **This is the only valid headless flag.** `--headless`, `CLAUDE_HEADLESS=true`, `--batch` and "CI mode" are **invented distractors**, and a longer timeout won't help.
- **Machine-readable output:** later pipeline steps need JSON, not prose. Use **`--output-format json`** together with **`--json-schema <schema>`** to enforce the shape, then parse it, for example with `jq` to **block the merge on critical findings**.
- **Session isolation:** reviewing in the **same session** that wrote the code is biased, because Claude rationalizes its own reasoning. **Each CI review step gets a fresh session**, the way a tester brings fresh eyes.
- **CLAUDE.md as the shared anchor for CI:** put code standards, review criteria, security policies and **testing conventions** (naming, mocking, coverage) in the project CLAUDE.md. Every fresh CI session inherits them automatically, and generated tests come out consistent.
- **Deduplicating review comments:** each new CI run is a fresh session that has forgotten its earlier reviews. **Fetch earlier review comments (for example with `gh`) and pass them into the prompt** so Claude only comments on new issues.

**Production pipeline shape:**
1. Project context from CLAUDE.md
2. Load earlier findings
3. Fresh session with `claude -p`
4. `--output-format json --json-schema`
5. Act on the result, for example block the merge if severity is critical

### Domain 3: exam signals
- "Contents" → **Grep**; "paths or names" → **Glob**; "Edit failed, text not unique" → **Read + Write**
- "Read all files first" → **wrong**; use incremental exploration
- "Teammate's Claude ignores conventions" → **CLAUDE.md is in user scope; move it to the project**
- "Different rules per file type" → **`.claude/rules/` + `paths`**
- "Check what's loaded" → **`/memory`**
- "Command for every contributor" → **`.claude/commands/`**
- "Skill floods the main context" → **`context: fork`**; "limit a skill's tools" → **`allowed-tools`**
- "Large or irreversible migration" → **plan mode**
- "CI job hangs" → **`-p` / `--print`**
- "Downstream step needs JSON" → **`--output-format json` + `--json-schema`**
- "Duplicate PR comments each run" → **pass earlier findings into the new session**

### Domain 3: scenario drills

**Q13.** A team wants `/review-pr` to be available automatically to every developer who clones the repo. Where should it go?
<details><summary>Answer</summary>

`.claude/commands/review-pr.md` in the **project repository**, committed. Not `~/.claude/commands/`, which is personal, and not CLAUDE.md, which is for ambient rules, not on-demand commands.
</details>

**Q14.** A repo has Terraform under `infra/` and React under `web/`. You want security rules applied only to Terraform files and testing conventions only to `*.test.tsx`, without cluttering CLAUDE.md. Best setup?
<details><summary>Answer</summary>

Separate files in **`.claude/rules/`** with YAML `paths` frontmatter (`infra/**/*`, `**/*.test.tsx`), so each one loads conditionally. `@import` loads unconditionally, and directory CLAUDE.md files are scoped by directory, not by file pattern.
</details>

**Q15.** Claude Code is asked to find where authentication happens in a 200k-line repo it has never seen. It starts reading every `.py` file one by one. Better approach?
<details><summary>Answer</summary>

**Grep** for auth-related terms (contents) and **Glob** to narrow by path pattern, then **Read** only the handful of relevant files and trace from there. Bulk reading exhausts the context window. Note that Glob doesn't search file contents.
</details>

**Q16.** A GitHub Action calling Claude Code hangs on its first run until it times out. Fix?
<details><summary>Answer</summary>

Use **`claude -p "<prompt>"`** (`--print`) for non-interactive mode. `--headless`, `CLAUDE_HEADLESS` and `--batch` don't exist, and a longer timeout doesn't fix a prompt that's waiting for input.
</details>

**Q17.** A developer asks Claude Code to split a 40,000-line monolith into three microservices with no predefined boundaries. Direct execution or plan mode?
<details><summary>Answer</summary>

**Plan mode.** It's a large, architectural, hard-to-reverse change with several valid approaches. Plan first, approve, then execute. Direct execution would start editing files before any coherent plan exists.
</details>

---

## Domain 4 – Prompt Engineering & Structured Output (~20%)

### 4.1 Explicit criteria over vague judgment `[Ep 14]`
**Scenario:** an AI code reviewer flags about 47 issues per PR, mostly noise. Developers stop reading it, and a real SQL injection at item #23 gets merged.

- **Trust collapse is holistic:** once developers learn to ignore the bot, they ignore **every** category, including the real security findings. False positives are actively dangerous, not just annoying.
- ❌ **Vague instructions** like "be thorough and conservative" don't improve precision. The model can't tell what "conservative" means relative to *your* standards.
- ❌ **Confidence thresholds** like "only flag issues you're 80% confident about" don't work either. The model's confidence is calibrated to its **training data**, not your codebase. It may be very sure about a naming nit and less sure about real SQL injection.
- ✅ **Categorical criteria:** stop asking for judgment and **say exactly what to report and what to skip**:
  - **Report:** critical (SQL injection, XSS, CSRF), error (missing error handlers on critical paths, race conditions), security (hard-coded credentials, weak crypto)
  - **Never report:** style already approved by the linter, naming conventions, sub-5 ms micro-optimizations, nitpicks
  - **Format:** for example, a JSON array of `{severity, file, line, message}`
- **Explicit severity levels, illustrated with code examples:** this builds toward few-shot prompting.
- **The "nuclear option":** if one category (for example performance) keeps producing false positives, **temporarily disable that category** to rebuild trust, then bring it back with better criteria and examples. **Lowering the overall threshold is the wrong move.**

**Same principle in extraction (scenario 6):** a model that "fills gaps" invents patient IDs, diagnosis codes or dosages. Say exactly what to extract and what to skip: **never fabricate; if a value is missing, return `null`; if it's ambiguous, return the raw text.** A null is a valid answer; an invented ID can mean a lawsuit.

### 4.2 Few-shot prompting `[Ep 15]`
- **Demonstration beats description.** Instructions say *what* you want; examples **show** it. Few-shot examples work better than long prose definitions, and more prose just adds more room for ambiguity. Words like "severe" get interpreted against training data, not your labels.
- **Structure of a good example: input + reasoning + output.**
  - The output tells the model **what** to answer.
  - The reasoning tells it **how** to get there, which lets it **generalize**.
  - Output-only examples lead to **surface pattern-matching**, a bit like overfitting.
- **The 2–4 example rule:** use **2–4 targeted examples**.
  - 5–8 or more causes **pattern-matching and context bloat**.
  - Too few gives too little coverage.
- **Target the fault lines:** run about 10 inputs 3× each, find where the outputs **flip or drift**, and write examples for **those ambiguous boundary cases**, not the obvious ones.
- **Applications:**
  - CI reviewer: one example each for critical, high and medium, with the reasoning.
  - Extraction: one example from a **table-format** document and one from a **prose-paragraph** document.
  - Support agent: examples on either side of the resolve-vs-escalate boundary, such as long-tenure billing discrepancy → resolve; repeated failure plus failed earlier contact → escalate.
- **Order of fixes for agents:** **fix the tool descriptions first, then add few-shot examples.** If the wrong tool is picked, examples can't help.
- **Distractors:**
  - "Lower the temperature" controls randomness, not judgment.
  - "Add 6–8 examples" causes bloat and pattern-matching.
  - "Few-shot for **compliance**" is wrong: few-shot is for **consistency**, and guarantees need hooks.

**First step vs improvement:** for false positives, the **first step** is **categorical criteria**; **few-shot examples** improve consistency **after** that.

### 4.3 Structured output with `tool_use` `[Ep 16]`
**Why free-form "return JSON" prompting breaks pipelines:**
- **Markdown wrapping**: the model wraps the JSON in code fences, which breaks the parser.
- **Schema drift**: optional fields go missing, keys get renamed, nesting changes.
- **Fabrication** of required fields.

**The "fake tool" pattern:** define a tool **whose only job is to receive a structured payload** through its `input_schema` (for example `extract_invoice_data` with `vendor_name`, `total_amount`, `invoice_date`). The API makes the model's tool call match the schema, and you read `response.content[0].input` as a clean dictionary. Combine it with **`tool_choice: any`**, or force the specific tool, so a tool call is **guaranteed**.

**Required + nullable: the honest way out**
- A required, **non-nullable** string field means the model **must produce a value**, so it **invents one** when the source doesn't have it.
- Use **`"type": ["string", "null"]`**: the field is guaranteed to be **present**, but `null` is allowed when the data really isn't there. This prevents fabrication.

### 4.4 Syntax vs semantics `[Ep 16]`
| | Syntax / structural errors | Semantic errors |
|---|---|---|
| Examples | Missing required field, string instead of number, malformed JSON | Reading the **wrong table row**, mixing up due date and invoice date, hallucinated values |
| Fixed by | **Strict JSON schema + tool_use enforcement** | **Business-rule validation, cross-field consistency checks** (does the total equal the sum of line items?), **human review**, and validation in post-tool hooks |

> A schema guarantees **structure**, not **truth**. Perfectly valid JSON can still be factually wrong.

### 4.5 The self-correcting retry loop `[Ep 16]`
1. Extract.
2. Validate.
3. If validation fails, append the **specific** validation error (for example "invoice_date must be YYYY-MM-DD; got '3rd May'") to the conversation as feedback.
4. Retry, up to a maximum number of attempts.

- **Retries fix *format*, not *missing information*.** If a field isn't in the document, more retries will never find it, and pushing harder **encourages hallucination**.
- **Fix for "fails on every retry because the data is really missing":** **make the field nullable** and send those documents to human review.
- Generic feedback ("validation failed") produces the same failure again. Make the feedback **specific**.

### 4.6 Message Batches API `[Ep 17, 13]`
- **50% cheaper**, same model and same quality, but **asynchronous**, with processing **within 24 hours** and **no latency SLA**.
- **Each request runs as a single turn:** you can't run a back-and-forth tool loop inside a batch request. No streaming.
- **`custom_id`** links each request to its result. Use **meaningful, deterministic IDs** such as `pr-1234-src/auth.py-v2`, not random UUIDs.
- **Decision rule:**
  1. Is a person or pipeline **waiting** for this result? → **Standard API.**
  2. Does it need **multi-turn tool calling**? → **Standard API.**
  3. Otherwise → **Batch API**: overnight reports, nightly test generation, security audits, processing 500 invoices on a Sunday, weekly feedback classification.
- ❌ **Never use batches for blocking workflows**, such as pre-merge CI checks that block a PR. This is official sample question 11.

### 4.7 Multi-pass and independent review `[Ep 17, 13]`
- **Self-review is biased:** a Claude instance reviewing its own output still has its original reasoning in context. Use an **independent instance or session** to review, with fresh eyes. To keep the cost down, give the reviewer a compact functional summary rather than the whole history.
- **Multi-pass architecture for large PRs:**
  - **Per-file passes** (one instance per file, can run in parallel) give **depth**.
  - A **cross-file integration pass** over the combined findings gives **breadth**: renamed functions breaking callers, broken imports or exports.
- **Exam answer for "a 14-file PR reviewed in one pass gives inconsistent feedback and misses cross-file bugs":** **per-file passes plus an integration pass.** Not "be thorough", not reviewing twice and averaging, not more max tokens.
- **Combined enterprise picture:**
  - Blocking PR review = **standard API**, multi-pass, earlier findings passed in.
  - Nightly test generation and audits = **Batch API**.
  - **Self-review nowhere.**

### Domain 4: exam signals
- "Too many false positives / be conservative / only high-confidence" → **categorical criteria**, and disable the noisy category
- "Inconsistent labels for the same bug class" → **2–4 few-shot examples with reasoning**
- "Guaranteed JSON shape" → **tool_use + JSON schema + `tool_choice` any or forced**
- "Model invents missing values" → **required + nullable fields**
- "Valid JSON but wrong values" → **semantic validation**, not more retries or stricter schemas
- "Retries fail every time because the field is missing" → **make it nullable + human review**
- "Cut cost of nightly or non-urgent jobs" → **Batch API**; "blocking CI" → **never batch**
- "Correlate batch results" → **`custom_id`**
- "Same instance reviews its own code" → **independent instance**

### Domain 4: scenario drills

**Q18.** An extraction pipeline uses tool_use with a strict schema. On 4% of scanned invoices, `due_date` is a believable but **invented** date that isn't anywhere in the document. The team retries on validation failure. Will more retries help?
<details><summary>Answer</summary>

**No.** Retries fix format, not missing information. Make `due_date` **nullable** (`["string","null"]`) so the model can return null, and send those documents to human review.
</details>

**Q19.** A team wants to move a **blocking** pre-merge PR review to the Message Batches API to save 50%. What's wrong?
<details><summary>Answer</summary>

Batches have **no latency SLA** and take up to 24 hours, so a blocking check could stall PRs for a day. Keep blocking workflows on the standard API; use batches for non-blocking jobs such as nightly test generation.
</details>

**Q20.** A CI reviewer assigns different severities to the same bug class on different runs. The prompt already has 600 words of prose definitions. Most effective fix?
<details><summary>Answer</summary>

**2–4 targeted few-shot examples, each with input, reasoning and severity**, chosen at the boundaries where labels flip. More prose, lower temperature or 6–8 examples are distractors.
</details>

---

## Domain 5 – Context Management & Reliability (~15%)

### 5.1 The context window as working memory `[Ep 18]`
- Everything shares one limited space: **system prompt + every message + tool calls + tool results**, measured in tokens.
- The API is **stateless**: you send the whole conversation each time, so **context management is required by the architecture**.

**Why agents "forget":**
- **Progressive summarization loses precision.** "Customer reported delivery issues, wants a refund" has lost the order number, the $149 amount and the dates the agent needed.
  - Losing numbers, dates or policy thresholds is a **reliability failure**, not an efficiency trade-off.
- **Lost in the middle:** LLMs pay most attention to the **beginning and end** of the context and less to the middle.
- **Tool results quietly consume context:** about 2–3k tokens per loop iteration × 20 iterations = 40–50k tokens, mostly noise.

**Fixes:**
- **Case facts block:** a compact (about 200-token) block of **verified** transactional facts (customer ID, order ID, item, amount, dates, policy window), **kept up to date** and placed **at the top** of the context where attention is highest. Pull these facts out of tool results with a **PostToolUse hook**; a regex is often enough, no AI needed.
- **Trim first, then pass:** filter verbose tool output **at the hook layer, before it builds up**. Cleaning up after the context is already bloated doesn't work.
- **Context layout:**
  - **Top:** case facts
  - **Middle:** trimmed, relevant tool results
  - **End:** a critical recap, the policy rules and the current question

### 5.2 When to escalate to a human `[Ep 18, Bonus]`
**Valid triggers**
1. **The customer explicitly asks for a human.** **Escalate immediately.** Don't try to resolve it first, and don't ask why.
2. **Policy gap or exception:** no clear policy covers the case, or it exceeds the agent's authority (for example a refund over $500).
3. **Agent stuck:** no progress after a set number of attempts or retries.

**Invalid triggers (traps)**
- **Negative sentiment alone**: an angry customer whose request falls within policy should still be handled by the agent.
- **Task complexity alone**: complicated but within policy and capability means the agent keeps going.
- **The model's self-reported confidence**: not calibrated to actual accuracy.

**Decision flow:**
1. Explicit request? → escalate now.
2. Otherwise, is it covered by policy? If not → escalate.
3. If covered, is the agent stuck after N attempts? If yes → escalate; if not → keep working.

> Escalation is **not** a fallback for hard problems. Implement it as an `escalate_to_human` tool with a clear description, ideally with a **structured handoff summary**.

### 5.3 Error propagation from sub-agent to coordinator `[Ep 19]`
- Domain 2 covered **tool → agent** errors (`isError`). This section covers **sub-agent → coordinator** errors.
- **Vague errors leave the coordinator stuck.** "Operation failed" doesn't say whether to retry, reroute or escalate.
- **A recovery-ready error response includes:**
  1. **Error category**: timeout, permission, invalid input, policy
  2. **`isRetryable`**
  3. **Attempted query**: what the sub-agent was trying to do
  4. **Partial results + alternatives**: what it *did* get (for example 3 of 5 documents), which the coordinator should keep and not throw away, plus fallback sources to try
- **Access failure ≠ valid empty result.** The library analogy:
  - **Database down** → *access failure*, retryable, **try again later or use a backup source**.
  - **Search worked, no book exists** → *valid empty result*, **not retryable**.
  - Treating these the same either wastes retries or gives up on queries that would have worked.
- **Two anti-patterns (tested):**
  1. **Silent suppression**: an exception is caught and reported as `status: ok, results: []`, producing confidently wrong reports. This is the worst kind of failure.
  2. **Immediate termination**: one sub-agent failure aborts the whole pipeline and throws away the other agents' work. **Only the coordinator decides to terminate.**
- **Local recovery first:** retry transient errors, adjust the query for format problems, try a backup source, and only then escalate to the coordinator.

### 5.4 Long Claude Code sessions: scratchpad, `/compact`, manifest `[Ep 19]`
| Technique | What it does | Notes |
|---|---|---|
| **Scratchpad file** (for example `.claude/scratchpad.md`) | Claude writes key findings to a file **on disk** as it explores, and **re-reads it** after early context drops out, instead of re-reading source files | **Must be asked for explicitly**: in the prompt for interactive use, **in CLAUDE.md for CI**, or in code for programmatic agents |
| **`/compact`** | Compresses the conversation history into a summary to free up context | Typed interactively, and runs automatically near the context limit. **Not available as a command inside a `-p` CI run** (per the course) |
| **Manifest file** (for example `.claude/manifest.json`) | A **checkpoint**: before each major step, Claude writes its current state to a **fixed, predictable path**. After a crash, restart and point it at the manifest to **continue from where it stopped** | Like a Git commit for agent progress. The scratchpad records *what was learned*; the manifest records *where you are* |

- Keep these files in a **predictable location**, such as inside `.claude/`, so Claude doesn't waste tokens looking for them.
- **Layers of a robust system:**
  - **Error layer:** structured error propagation
  - **Context layer:** scratchpad + `/compact`
  - **Recovery layer:** manifest checkpoints

### 5.5 Human review workflows: stratified sampling `[Ep 20]`
- **The 97% accuracy trap:** overall accuracy is dominated by the **high-volume, easy** cases (standard PDF invoices) and **hides** a category that keeps failing (handwritten receipts at **60%**). Low volume doesn't mean low stakes, and consistent failure on one category is a **systematic** problem, not noise.
- **Stratified sampling:**
  1. **Categorize** documents into strata.
  2. **Sample from every stratum**, including small ones.
  3. **Human-review the samples and measure accuracy by category.**
  4. **Act**, for example by sending every handwritten receipt to humans.

  This shows *where* the AI fails without reviewing everything, like a car factory testing samples from each production line.
- **Field-level confidence:** confidence belongs to **each field**, not the whole document. For example: invoice # 0.97, amount 0.91, vendor address 0.63 (handwritten). **Only the low-confidence field goes to a human.**
  - Confidence must be **calibrated against labeled validation sets** (known ground truth). Raw self-reported confidence is just a guess.
- **Routing triggers to the human queue:**
  1. Any field **below the confidence threshold**
  2. **Contradictory fields**: the total doesn't match the line items, or a date is in the future
- **Two anti-patterns:**
  1. **Silently discarding** low-confidence fields, leaving gaps that downstream systems don't know about
  2. **Forcing them through** without a flag, contaminating downstream data with no audit trail

### 5.6 Information provenance `[Ep 20]`
- **Claim-source mappings must survive across every agent boundary:**
  - **Search agent:** URL, publication date, domain credibility
  - **Analysis agent:** keeps page numbers and sections
  - **Synthesis agent:** **highest-risk point.** It must not merge multiple sources into one untagged claim; it needs source tags in its prompt and output schema
  - **Report agent:** full citations, so the reader can trace every claim
- **Conflicting values** (for example market size $12B vs $18B from different sources): **don't pick the highest or lowest and don't average them**, since an average is itself an invented number. **Annotate both with their sources and send the conflict to the coordinator or a human.**
- **Temporal data:** a 2019 figure isn't a 2024 figure. **Require `publication_date` and `collection_date` in structured outputs.** The fix is a **schema change**, not prompt engineering or retry logic.

### Domain 5: exam signals
- "Agent forgets amounts or IDs in long conversations" → **case facts block at the top + trim tool results with PostToolUse hooks**
- "Summarization lost numbers" → **reliability failure; keep facts in a structured block**
- "Customer asks for a human" → **escalate immediately**
- "Escalate on low confidence or anger" → **trap**
- "Coordinator can't tell transient from empty" → **structured error context with category, retryable, attempted query, partial results, alternatives**
- "Sub-agent failure kills the pipeline" → **anti-pattern; propagate, let the coordinator decide**
- "Context dropped in a long session" → **scratchpad file**; "resume after a crash" → **manifest checkpoint**
- "High overall accuracy but complaints about one category" → **stratified sampling + field-level confidence**
- "Two sources disagree" → **annotate both and escalate**
- "Stale statistics" → **publication and collection dates in the schema**

### Domain 5: scenario drills

**Q21.** A customer, 12 months with you, angry about a confirmed damaged and late order, writes: "I just want to speak to an actual person." What should the agent do?
<details><summary>Answer</summary>

**Transfer to a human immediately**, with a structured handoff. Don't attempt another fix, don't ask why, and don't point them to self-service. An explicit request is the golden rule.
</details>

**Q22.** An agent escalates whenever its self-reported confidence drops below 70%. Easy cases get escalated and some complex billing disputes are resolved wrongly. Most reliable fix?
<details><summary>Answer</summary>

**Replace confidence with explicit, observable criteria:** an explicit request for a human, a known policy gap or exception, or no progress after N attempts. Lowering the threshold, averaging two confidence scores, or removing escalation are all distractors.
</details>

**Q23.** A document sub-agent returns an empty result both when retrieval fails over the network and when the document truly has no relevant content. The coordinator tells users "no information found" even after network failures. Fix?
<details><summary>Answer</summary>

Return **structured error context** that separates a **transient access failure** (retryable, with attempted query and alternatives) from a **valid empty result**, so the coordinator can retry, use a fallback or report correctly. Silent retries that still return empty don't fix it.
</details>

**Q24.** An extraction system processes 10k documents a day at 96% overall accuracy and auto-routes anything with document-level confidence above 0.80. Errors keep appearing in legal contracts. Root cause?
<details><summary>Answer</summary>

**Document-level confidence and the overall average hide failures in one category.** Use **stratified sampling by document type** and **field-level confidence calibrated on labeled data**, and send low-confidence or contradictory fields to humans. It's not a few-shot or prompt problem, and errors at 96% aren't simply "expected".
</details>

---

## 6. Mixed Practice Exam

Try each question before opening the answer. Pay attention to which distractor trap each wrong option uses.

**P1.** A coordinator delegates to three research sub-agents. The final report repeatedly includes the same facts three times, and none of the sub-agents seem to know what the others found. Root cause?
<details><summary>Answer</summary>Sub-agents start with blank context and the coordinator isn't injecting the relevant context, including scope boundaries, into each Task prompt. Don't let sub-agents message each other: everything goes through the coordinator.</details>

**P2.** Which `stop_reason` value is the only valid primary exit from an agentic loop?
<details><summary>Answer</summary>`end_turn`. The iteration cap is a safety valve only.</details>

**P3.** A worker sub-agent has `Task` in its `allowedTools` and keeps spawning more workers. What principle is being broken, and when is this allowed?
<details><summary>Answer</summary>Hub-and-spoke: workers shouldn't spawn agents. It's only allowed for a hierarchical sub-coordinator deliberately designed to delegate to a deeper layer.</details>

**P4.** Your support agent must **never** process a refund for an unverified customer. Which answer is right: (a) put "NEVER" in capitals in the system prompt, (b) few-shot examples, (c) a PreToolUse gate checking a `verified` session flag, (d) a classifier sub-agent?
<details><summary>Answer</summary>(c). "Never" means a guarantee, which means a hook. (a) and (b) are probabilistic, and (d) is premature infrastructure.</details>

**P5.** An MCP search tool you added is ignored; Claude keeps using its built-in Grep. First fix?
<details><summary>Answer</summary>Improve the MCP tool's description, saying when to use it instead of grep (for example "semantic or intent search"). You can do this through a description override in `.mcp.json`.</details>

**P6.** You need every call to return data in one specific schema, with no prose answers. Which `tool_choice`?
<details><summary>Answer</summary>`{"type":"tool","name":"<extraction_tool>"}` for one specific schema, or `{"type":"any"}` when any of several extraction tools is fine. `auto` may answer in text.</details>

**P7.** A tool returns a validation error because the date format was wrong. Retryable?
<details><summary>Answer</summary>Not with the same input. Correct the input, then a retry can succeed. Pick the option that fixes the validation issue rather than blindly retrying.</details>

**P8.** Teammates pull the repo and none of the project's MCP servers appear. Fix?
<details><summary>Answer</summary>Move the server config from `~/.claude.json` (personal) to `.mcp.json` at the project root and commit it, with secrets as `${ENV_VAR}`.</details>

**P9.** Edit fails with "old_string matches multiple locations". Recovery?
<details><summary>Answer</summary>Use a longer, unique anchor; if that's not possible, fall back to Read the whole file, change it, and Write it back.</details>

**P10.** A personal pre-push checklist command you use across all your projects. Where does it go?
<details><summary>Answer</summary>`~/.claude/commands/` (user scope).</details>

**P11.** How do you confirm which CLAUDE.md and rules files are loaded in the current session?
<details><summary>Answer</summary>`/memory`.</details>

**P12.** You need Claude Code to output JSON matching `review-schema.json` in GitHub Actions. Command shape?
<details><summary>Answer</summary>`claude -p "<prompt>" --output-format json --json-schema review-schema.json > findings.json`, then parse it (for example with `jq`) and fail the job on critical severity.</details>

**P13.** Each CI run re-posts the same review comments on a PR. Fix?
<details><summary>Answer</summary>Load earlier review comments (for example `gh pr view --comments`) and include them in the new session's prompt, telling it to report only new issues.</details>

**P14.** A reviewer flags 50 items per PR, developers ignore it, and a SQL injection slips through. First step?
<details><summary>Answer</summary>Replace vague instructions and confidence thresholds with explicit categorical criteria for what to report and skip, and temporarily disable the noisiest category. Few-shot examples come next, to improve consistency.</details>

**P15.** Schema validation passes 100% of the time, but amounts are sometimes taken from the wrong table row. Fix?
<details><summary>Answer</summary>Semantic validation: business rules and cross-field checks, such as line items adding up to the total, plus human review on mismatches. Stricter schemas and more retries can't fix how the document was read.</details>

**P16.** 2,000 customer feedback forms are collected each week. Each form is independent, no tools are needed, and results are needed by Monday. Standard or batch?
<details><summary>Answer</summary>Batch. Nothing is blocking, each request is a single turn and independent, so you save 50%. Use `custom_id` such as `feedback-2026w40-<form_id>`.</details>

**P17.** After 25 turns, a support agent issues a refund for the wrong amount; the original amount was summarized away. Fix?
<details><summary>Answer</summary>Keep a case facts block (IDs, amounts, dates, policy window) at the top of the context, extracted and trimmed from tool results by PostToolUse hooks, instead of relying on progressive summarization.</details>

**P18.** A sub-agent hits a single timeout and immediately raises an exception that ends the whole research pipeline. What should happen instead?
<details><summary>Answer</summary>Retry the transient error locally. If it still fails, return a structured error (category, retryable, attempted query, partial results, alternatives) to the coordinator, which decides whether to retry, reroute, escalate or end.</details>

**P19.** Two sources give the 2024 market size as $12B and $18B. What should the synthesis agent do?
<details><summary>Answer</summary>Keep both claims with their source attributions, record a conflict, and send it to the coordinator or a human. Don't pick one and don't average them.</details>

**P20.** A research pipeline's final report quotes a statistic that was true in 2019 as if it were current. Fix?
<details><summary>Answer</summary>Change the schema to make `publication_date` and `collection_date` required on every claim, so downstream steps can spot and flag stale data. This is not a prompt or retry fix.</details>

---

## 7. One-Page Cheat Sheet

### Decision rules
| If the question says… | Answer |
|---|---|
| guarantee / must / never / policy requires | **Hook** (PreToolUse gate). Not prompt wording, not few-shot |
| normalize or clean tool output before the model sees it | **PostToolUse hook** |
| X must run before Y | **Prerequisite gate** with a session flag |
| sub-agent output generic, duplicated or unaware | **Inject context explicitly** in the Task prompt |
| 3× slower than expected | **Multiple Task calls in one response** |
| report misses whole topics | **Decomposition too narrow** |
| steps known up front / unknown investigation | **Prompt chaining / dynamic decomposition** |
| attribution lost | **Claim-source mappings** |
| sources conflict | **Annotate both → coordinator or human** |
| same task, context still valid / parallel approaches / stale | **`--resume` + list changes / fork / fresh + hypotheses** |
| wrong tool chosen | **Better tool descriptions and names first** |
| failure treated as success | **`isError` + category + retryable + alternatives** |
| too many tools | **Scoped tool access** |
| guaranteed structured output | **tool_use schema + `tool_choice` any or forced** |
| teammates lack MCP servers / CLAUDE.md / commands | **Project scope**: `.mcp.json`, `./CLAUDE.md`, `.claude/commands/` |
| secrets in config | **`${ENV_VAR}`** |
| rules per file type | **`.claude/rules/` + `paths`** |
| what's loaded? | **`/memory`** |
| skill floods context | **`context: fork`** |
| contents vs paths | **Grep vs Glob** |
| Edit anchor not unique | **Read + Write** |
| large or irreversible change | **Plan mode** |
| context exhausted during exploration | **Explore sub-agent** |
| vague requirements | **Interview pattern** |
| CI hangs | **`claude -p` / `--print`** |
| false positives | **Categorical criteria + disable the noisy category** |
| inconsistent labels | **2–4 few-shot examples with reasoning** |
| invented values | **Required + nullable** |
| valid JSON, wrong values | **Semantic validation** |
| retries fail because data is missing | **Nullable + human review** |
| cheap, non-urgent, single-turn | **Batch API** (+ `custom_id`); never for blocking work |
| self-review | **Independent instance**; per-file + integration passes |
| agent forgets facts | **Case facts block at the top + trim with hooks** |
| when to escalate | **Explicit request / policy gap / stuck**. Never sentiment, complexity or confidence |
| empty vs failed | **Structured error separating access failure from valid empty** |
| long session drops context / crash recovery | **Scratchpad / manifest** |
| overall accuracy hides failures | **Stratified sampling + calibrated field-level confidence** |
| stale data | **publication_date + collection_date in the schema** |

### Fake flags and settings to reject
`--headless` · `CLAUDE_HEADLESS=true` · `--batch` · "CI mode" · "set a priority flag on batch requests" · "batch API behaves the same as standard, only cheaper"

### Numbers to remember
- **720 / 1000** to pass · **120 min**
- **27 / 18 / 20 / 20 / 15 %** for domains 1–5
- Few-shot: **2–4** examples
- Batch: **−50%**, **≤24 h**, no SLA, single turn
- Example policy threshold in the course: **$500**

---

*These notes were written from the course transcripts. Check product details (flags, file paths, tool names) against the current official exam guide and the Claude Code and Agent SDK documentation, since they change over time.*
