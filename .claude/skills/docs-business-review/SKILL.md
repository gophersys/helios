---
name: docs-business-review
description: Review and improve business-facing documentation for persuasion, clarity, and executive readability. Use for proposals, pitch docs, ROI analyses, and stakeholder communications.
user-invocable: true
argument-hint: "[file-path]"
---

# Business Document Review & Rewrite

Review a business-facing document and fix it. The goal is writing that persuades through clarity and evidence — not jargon, not corporate fluff, not word count.

**Target:** $ARGUMENTS

## Phase 1: Read & Diagnose

Read the entire document. For each section, note:

1. **Corporate fog** — Phrases that sound important but communicate nothing:
   - "Synergize cross-functional capabilities" → what does this actually mean?
   - "Drive alignment across stakeholders" → who needs to agree on what?
   - "Best-in-class solution" → compared to what? by what measure?
   - "Transformative impact" → quantify it or cut it
   - "Strategic initiative" → every initiative is "strategic" in a proposal, the word is empty
   - "Unlock value" → how much value? for whom?
   - Any sentence that could appear in any company's doc without modification is too generic

2. **Missing the "so what?"**:
   - Technical facts without business impact ("The system processes 10K requests/sec" → so what? does that save money? prevent outages? enable a new product?)
   - Features listed without connecting to the reader's problem
   - Data presented without interpretation
   - Comparisons without a baseline ("50% faster" → than what?)

3. **Structure for busy readers**:
   - Is the ask/recommendation in the first paragraph? (If buried on page 3, the exec stopped reading on page 1)
   - Can someone skim headers and get 80% of the message?
   - Are numbers, dates, and dollar amounts scannable (not buried in paragraphs)?
   - Is there a clear "what do you want me to do?" at the end?

4. **Persuasion**:
   - Does the doc acknowledge trade-offs? (One-sided arguments lose trust)
   - Are claims supported by evidence, data, or credible references?
   - Is the audience defined? (Writing for a CTO is different from writing for a CFO)
   - Does it address the obvious objections before the reader thinks of them?

## Phase 2: Fix It

Apply fixes directly. Follow these principles:

### Voice
- Confident but not arrogant. State what's true. Acknowledge what's uncertain.
- Write for the most skeptical person in the room
- Numbers are more persuasive than adjectives ("reduced cost by $180K/year" beats "significantly reduced costs")
- Short paragraphs. One idea each. White space is your friend.

### Structure
- **Lead with the recommendation.** "We should do X because Y. Here's the evidence."
- Executive summary at the top if the doc is longer than 2 pages
- Problem → Impact → Solution → Evidence → Ask. This order works for 90% of business docs.
- Use headers that state the conclusion: "Build costs drop 40% with automated pipelines" not "Cost Analysis"

### Formatting
- Bold the single most important number or conclusion in each section
- Use tables for any comparison (cost, timeline, options)
- Pull quotes or callout boxes for key stats
- Keep the main doc short. Put supporting detail in appendices or linked docs.

### What NOT to do
- Don't pad with filler to look "thorough"
- Don't use passive voice to avoid ownership ("It was decided..." → "We decided..." or "I recommend...")
- Don't add emoji
- Don't change technical accuracy — only improve how it's communicated
- Don't add AI attribution

## Phase 3: Report

After editing, output a short summary:
- Key structural changes
- Top 3 recurring issues found
- Anything that needs input from the author (missing data, unclear audience, etc.)
