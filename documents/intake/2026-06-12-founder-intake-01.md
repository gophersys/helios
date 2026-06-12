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
