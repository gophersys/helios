---
name: docs-technical-review
description: Review and improve technical documentation for clarity, structure, flow, and human voice. Use when docs read robotic, overly verbose, or structurally weak.
user-invocable: true
argument-hint: "[file-path]"
---

# Technical Document Review & Rewrite

Review a technical document for quality, then fix it. The goal is documentation that reads like it was written by a sharp engineer who respects the reader's time — not by a committee, not by an AI.

**Target:** $ARGUMENTS

## Phase 1: Read & Diagnose

Read the entire document. For each section, note:

1. **Robot voice** — Phrases no human would say out loud. Examples of what to kill:
   - "It is important to note that..." → just say the thing
   - "This section describes..." → remove, let the content speak
   - "In order to..." → "To..."
   - "Utilize" → "use"
   - "Facilitate" → "enable" or just cut it
   - "Leverage" (as a verb) → "use"
   - "It should be noted that" → delete entirely
   - Passive voice where active is clearer: "The pipeline is triggered by..." → "Webhooks trigger the pipeline"
   - Redundant hedging: "This essentially means..." → just state it

2. **Structure problems**:
   - Sections that are just lists with no connective tissue
   - Headers that don't tell you what you'll learn (e.g., "Overview" says nothing)
   - Missing transitions between sections (reader has to figure out why section B follows section A)
   - Information buried in the wrong section
   - Tables that should be prose, or prose that should be tables

3. **Flow & rhythm**:
   - Three long sentences in a row → vary sentence length
   - Every paragraph starting the same way
   - Walls of text with no breathing room
   - Bullet lists used as a crutch to avoid writing real paragraphs
   - No "so what?" — technical facts stated without connecting to why the reader should care

4. **Substance**:
   - Claims without evidence or examples
   - Vague statements that sound authoritative but say nothing ("This is critical for success")
   - Missing context — assumes reader knowledge that wasn't established
   - Jargon used without definition on first appearance

## Phase 2: Fix It

Apply fixes directly to the document. Follow these principles:

### Voice
- Write like you're explaining to a smart colleague at a whiteboard
- First person plural ("we") is fine for team docs. "You" for guides.
- Short sentences for important points. Longer ones for context and nuance.
- One idea per paragraph. If a paragraph has two ideas, split it.
- Lead with the point, then support it. Never build up to a reveal.

### Structure
- Every heading should be a complete thought or question the section answers
- Use transitions: "This creates a problem:" / "The fix is straightforward:" / "But there's a catch."
- Front-load each section — the first sentence should tell the reader whether to keep reading or skip
- Group related content. If you mention something, finish talking about it before moving on.

### Formatting
- Bold key terms on first use, not every use
- Code blocks for anything the reader would type or reference literally
- Tables for comparisons and reference data. Prose for arguments and explanations.
- Keep bullet lists to 3-7 items. More than 7 means you need subcategories or prose.

### What NOT to do
- Don't add filler to make it longer
- Don't add emoji
- Don't soften direct statements ("arguably", "perhaps", "it could be said")
- Don't restructure sections that already flow well — only fix what's broken
- Don't change technical content or meaning — only improve how it's expressed
- Don't add AI attribution or meta-commentary about the editing process

## Phase 3: Report

After editing, output a short summary:
- Number of sections edited vs. left alone
- Top 3 recurring issues found
- Any structural changes made (sections moved, merged, or split)
