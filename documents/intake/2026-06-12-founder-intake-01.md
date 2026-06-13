# Founder intake — session 01

> Source: Mateo, 2026-06-12 (verbatim; typos preserved — this is provenance, not prose).
> Referenced by product-tier documents as `source: {run: founder-intake-01, span: C<n>}`.

## Verbatim

> the founder who doesnt really know much about architecture but has a product vision, wants to
> be able to create cheap poc that "just works" only for him to test the product, then a small
> test run with actual test users, and then 1000+ user production deployments, each running on a
> differnt cloud hosted environment. if the user does not want to provide their own
> infrastrucute god mode api keys, then they will run on helios infrastructure and get charged
> for it. even when running on desktop, the compute runs from a cluster that the user points to.
> this cluster can be anything from the development environments where the agents run as pods,
> to where the user vscode instance runs with the right gates to prevent damaage to the code, to
> the ci action runners, and it must cheap and scalable, so helios has 1 central eks cluster for
> all its users, BUT, if the user chooses the sellf hosted option, they can connect their
> cluster, or their cloud or whatever. you understnad? so the option to set it and forget it
> exists, but we strongly enmcoruage users to use their own infrasturcure and whatever, so that
> advanced users who are picky, only use the helios backend for organziation data about their
> poejrcts, but their repos and whatever is all on their platforms, and helios is just XTEMELY
> WELL GIT INTEGRATED as tio know what dirfeytd between repo and what we know exists. also the
> paltform must have incredible great poracites about git versoiing and releases, release cycles
> etc. maintaince and bug report fixes, things that a normal non technical founder must htink
> about, but htat a highly technical person would cream themselves to actually have present in
> their projects, so much that itr geunienly saves s much time. the other thjing too is we have
> to do an incredibly dep resarch and thinking baout how to present he user iinterface to the
> user, how to display documetns to read in a clear ogranized way, donwload documetns, view
> architecture diaagrams, see navigation patterns, observe production systems using these same
> diuargams, add feaures, all of that, its going to be a platform that feel slike ableton, where
> the ui is deep, detailes and theres a way to do thing. yiou have to do a in app turotual or
> watch the youtube videos to know what yorue doing, becauyse this is a mega fucking tool,
> peopel are ecorus to used desktop for full screen, but web works jsut fine,. does thios help?
> asl me more questions, remeber, pluggability, extensibily,a ndnbusng it self to build itself
> is a requiements as so to prove that the project odes work and can code anything. froma core
> set of opinionated concepts and arhcitecutre deicisons that then allow us to encapsulate user
> business data for their product implementation using these tempaltes, so a high level
> arhcitect is known, and can be maintined with the ai instrumentaiton for that version of the
> libraries/monorepo/devenvionemtns etc. the central part of helipos is the orcehstrator, which
> is what manages the users projects, etc etc. we have to hink deeply about api keys from
> proivders too, how to declare interfaces for infrastucurre so that anything from k3s to eks to
> do k8s works, u dunderat? ask me, compelte, think cohesive, push back, architecture work type
> of htings lets go, dont lose any data always asvwe and push

## Extracted claims (cite as C1…C16)

- **C1** Primary persona: a founder with product vision and little architecture knowledge.
- **C2** Maturity ladder: cheap founder-only PoC that "just works" → small cohort of real test
  users → 1000+ user production deployments, each on a different cloud-hosted environment.
- **C3** Default compute: users without their own infrastructure credentials run on the
  platform's hosted infrastructure, metered and charged.
- **C4** The client (web or desktop) is a control surface; compute always runs on a cluster the
  user points at.
- **C5** That cluster hosts everything: agent pods, the user's remote VS Code workspaces (with
  gates preventing damage), CI runners. Must be cheap and scalable.
- **C6** One central multi-tenant EKS cluster serves all hosted users; self-hosted users connect
  their own cluster or cloud instead.
- **C7** "Set it and forget it" exists, but BYO infrastructure is strongly encouraged.
- **C8** Advanced mode: the platform backend holds only organizational data about projects;
  repos and everything else live on the user's platforms; the platform is extremely well
  git-integrated and knows what drifted between their repo and known state.
- **C9** World-class release engineering as a product feature: git versioning, releases, release
  cycles, maintenance, bug-report-to-fix flows — invisible burden lifted from non-technical
  founders, delight for technical ones; genuinely time-saving.
- **C10** Deep UI research required: document reading/downloading in clear organization,
  architecture diagrams, navigation patterns, observing production systems through the same
  diagrams used for design, adding features from those views.
- **C11** Feel: Ableton-like — deep, detailed, "there's a way to do things"; learnable via
  in-app tutorial or videos; a mega-tool. Desktop encouraged for full-screen; web works fine.
- **C12** Pluggability, extensibility, and self-building (Eden builds Eden) are requirements —
  the proof the platform can code anything.
- **C13** A core set of opinionated concepts/architecture decisions encapsulates user business
  data into templates, so a high-level architecture is always known and maintainable by the AI
  instrumentation for that version of libraries/monorepo/dev-environments.
- **C14** The orchestrator is the central component — it manages user projects.
- **C15** Provider API keys need deep thought; infrastructure interfaces must be declared such
  that anything from k3s to EKS to DO kubernetes works.
- **C16** Standing directives: ask more questions, push back, stay cohesive; never lose data —
  always save and push.

## Session 01b — structured rulings (same day, follow-up Q&A)

- **C17** Fleet model: BOTH classic one-deployment SaaS and per-customer isolated deployments;
  fleet (one change rolled across N customer environments, each gated) is the headline
  capability.
- **C18** BYO-git gate enforcement is a per-project choice: enforced (Eden installed as a
  GitHub/GitLab app — required status checks, branch protection, Eden-run verification) or
  advisory (observe/report only); the dashboard permanently displays which guarantees are off.
- **C19** Compute posture: hosted-default, local-as-a-cluster — the central metered multi-tenant
  cluster is the default path; a local k3d/kind cluster is fully supported as just-another
  cluster (free PoCs, offline, Eden's own dogfooding); BYO strongly encouraged. Amends
  ADR-0006's local-first ruling.
- **C20** The first end-to-end demo is the founder PoC journey: wizard conversation → documents
  → generated system → cheap PoC deployed on a cluster → observable in the dashboard. Self-build
  continues underneath as the build method (the ladder), not the demo.

## Session 01c — design assets (same day)

- **C21** Visual identity provided as `2026-06-12-design-assets.pdf` (this directory): palette —
  Deep Forest `#243D2C` (primary surface) · Moss `#5C7F5C` (signature accent) · Sage `#A8B89C`
  (soft support) · Bone `#F4F1E8` (background / text on dark) · Ink `#1A1A1A` (text on light);
  typography — "Three families. Three roles. Locked.": Fraunces (display: 96/Black, 64/SemiBold,
  H1 40/SemiBold, H2 28/Regular), Inter (text: lead 24, body 18, caption 14/Medium, micro
  12/SemiBold letterspaced), JetBrains Mono (code: 16/Regular). Directive: all Eden surfaces
  follow these colors, theme, and fonts.

## Session 01d — agent sessions and the chat surface (same day)

- **C22** The chat interface pulls the agent layer: agents run in isolated pods/containers on the
  backend and render in real time in a fully fledged chat surface comparable to the Claude app.
  The agent abstraction layer selects the right agent for the right phase; product design uses
  Claude Code with the Fable 5 model. Step 1 is defining the agentic interface: the
  instrumentation expected from underlying harnesses (event stream, token/cost metering), the
  tools they are equipped with, and the session controls. Credentials: wrap Claude via
  `setup-token` so a normal membership user (like Mateo) works from the start; configurable
  throughout. Prior art exists in Mateo's repositories (poc/agents auth/bridge work,
  poc/codingharness) and should be mined first.

## Session 01e — the build wave (same day)

- **C23** Build the Go library backend now, full TDD: secrets; sandbox libraries (docker AND
  kubernetes) where agents run; git clone and all repository actions; the agent start/stop/resume
  interface with agent configuration (skills, rules); full observability and data collection; a
  basic orchestrator managing agent spawn-up; agent templates (custom configurations + custom
  sandboxes). Frontend shows full chats, tool usage, skill invocation, file modification,
  branches, costs, thinking. The setup-token secret flows through the frontend+backend
  architecture. Go tests must spin up real containers and a local kubernetes cluster to test the
  docker/kubernetes features fully. Deliver an initial set of Go test utilities for full backend
  tests, plus Playwright forced-CRUD user-journey tests (objects created through the UI are
  destroyed through the UI before exit; nested creation tested). Libraries written uniformly per
  scalable-Go best practices; a formalized staged workflow with interface agreement and TDD
  throughout.

## Session 01f — quality bar and the chat scalability mandate (same day)

- **C24** After each build wave, launch a wave of reviewers and architects to ensure a cohesive,
  well-done library architecture and true test coverage — integration and end-to-end tests are
  highly valued, not optional. The agent-chat UI is the key feature for the system working
  long-term: observability, chat, thinking, and all available + meaningful data collection must
  be nailed and displayable in the frontend. Communication is server-triggered events, nicely
  displayed. The mechanism must be scalable and reliable in start/stop/resume for BOTH the agents
  and the data flow itself — a user may have hundreds of agents running per project at any time,
  and the UI must let them navigate down to any chat and watch it in real time. No shortcuts: all
  functions and features implemented and tested, Google-level software, Go 1.26.

## Session 01g — the libraries are the crown-jewel asset; enforce, don't just review (same day)

- **C25** Worry: bad or stale code, non-standardization, poorly written code, poorly written
  interfaces. The core libraries are everything — the core asset — and must be written to be
  maintainable, fully AI-instrumented, and ENFORCED against the rules when being developed from
  this repo. Implication (mine, Mateo's intent): review-after-the-fact is necessary but not
  sufficient; the standard must be mechanically enforced at authoring time (inside the agent edit
  loop) and at the commit/CI gate, so non-conformant code cannot enter. The `cfgtest` naming
  break that slipped Wave 3A is the proof: prompt guidance alone is porous; deterministic linters
  and authoring-time hooks are the teeth.

## Session 01h — unified git versioning/workflow standard + Notion-grade document rendering (2026-06-13)

- **C26** As the libraries finish, build the git versioning strategy with clear standards:
  naming conventions, worktrees, and workflows. Include MERGE AGENTS that fix errors, run testing
  and gates, and merge. Build it scalably so that for the docs everything is version-controlled,
  and the SAME system applies to the architecture and implementation processes as the platform
  scales. (Intent: one artifact-agnostic git workflow machine — branch/worktree/commit/gate/merge
  — parameterized by artifact class, agent-driven, uniform across docs/architecture/implementation.)
- **C27** The frontend must render the generated markdown documents in a phenomenal Notion-like
  style — per-project data, beautifully readable by the user. (Sharpens the document-workspace v0
  into a Notion-grade reading experience in the Eden design language, still consuming the
  projection seam.)
