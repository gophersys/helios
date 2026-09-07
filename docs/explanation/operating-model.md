# Operating model

Eden is designed for scientific research and software engineering. Both practices
share five concepts:

```text
intent → plan → work → evidence → decision
```

Research moves through question, plan, investigation, conclusion, and transfer.
Software moves through need, definition, build, verification, release, and
operation. These are evidence states, not waterfall phases: a decision can return
work to an earlier state.

The canonical definitions are `.eden/practices/research.json` and
`.eden/practices/software.json`.
Agents, Nx checks, and the future UI must read those files rather than copy their
content into prose.

Research classification follows the [OECD Frascati Manual](https://www.oecd.org/content/dam/oecd/en/publications/reports/2015/10/frascati-manual-2015_g1g57dcb/9789264239012-en.pdf).
Technology maturity may use [NASA Technology Readiness Levels](https://www.nasa.gov/directorates/somd/space-communications-navigation-program/technology-readiness-levels/).
Software engineering is aligned with [ISO 15288](https://www.iso.org/standard/81702.html),
[ISO 12207](https://www.iso.org/standard/90219.html), [ISO 29148](https://www.iso.org/standard/72089.html),
[NIST SSDF](https://csrc.nist.gov/pubs/sp/800/218/final), and
[DORA continuous delivery](https://dora.dev/capabilities/continuous-delivery/).

Eden is standards-aligned; this repository does not claim certification.
