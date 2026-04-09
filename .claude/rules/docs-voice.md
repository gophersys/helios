# Documentation Voice

When writing or editing files under `docs/` (excluding `docs/_internal/` and `docs/_archive/`), follow the Concord product voice.

## The Voice

Modeled on Anthropic and Stripe documentation. Short sentences. Declarative. Assumes the reader is technical and competent. Never explains what they already know — just tell them what they need to do and what the system does.

## Sentence Rules

1. **Lead with what it does, not what it is.** "A product scopes all builds, validation, and manufacturing" — not "A product is the top-level object in Concord."
2. **15–25 words per sentence for instructions.** Longer for explanations, but break at 35.
3. **Active voice, second person for instructions.** "Open the product detail page" — not "The product detail page can be opened."
4. **Imperative for actions.** "Add a revision." "Select the branch." "Click Save."
5. **One idea per sentence.** If you used "and" more than once, split it.

## Structure Rules

1. **Open with a single-sentence summary.** What does this page help you do? One line.
2. **Use bullets for lists of 3+.** Prose for 1–2 related items.
3. **Vary bullet length.** One bullet can be 5 words. The next can be 20. Uniform length is an AI tell.
4. **Headings state the topic, not describe it.** "Setup" not "How to set up". "What a revision defines" not "This section explains what a revision defines."
5. **Code blocks stand alone.** Don't narrate what the code does line-by-line. State the goal, show the code.
6. **Tables for structured comparisons.** Not for 2-column key/value — use bold labels inline.

## Tone

- **Matter-of-fact.** State how it works. No enthusiasm, no hedging.
- **Technically confident.** Don't say "you might want to" — say "use X when Y."
- **No marketing.** "Concord compiles firmware" not "Concord empowers teams to build firmware."
- **No AI filler.** If it sounds like ChatGPT wrote it, delete it and start over.

## Kill on Sight

- "It is important to note that"
- "In order to"
- "allows you to" → just use the verb
- "the process of" → cut
- "This section describes" → delete
- "provides", "enables", "facilitates", "represents"
- "Navigate to X in the sidebar" → "Open **X**"
- "comprehensive", "robust", "seamless", "streamlined"
- "leverage", "utilize" → "use"
- Any sentence that starts with "Concord provides..."
- Passive voice where active is clearer
- Examples that name specific products (Alpha, B0) — keep docs generic unless it's a tutorial

## Reference Examples

Good:
> Each PCB revision gets its own entry. Concord builds and validates firmware per revision.

> Commit lands on a watched branch → git poller detects it → build run triggers automatically.

> Per-product. Administrators grant access to individual team members.

Bad:
> Board revisions represent different versions of your PCB hardware. Each revision allows you to configure the specific firmware variant that should be compiled for that particular hardware configuration.

> The firmware repository integration enables seamless CI/CD workflows by automatically detecting new commits and triggering the appropriate build pipeline.
