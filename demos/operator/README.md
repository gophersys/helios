# demos/operator — the worked example

A playable replica of Ableton Live 12's Operator: 4-op FM in Web Audio, every
control bound to a 113-address parameter tree, geometry emitted by
`solve_layout.py` from measured anchors + real font advances, and proven by the
six-gate battery in `assemble.py`.

## Local-only requirements (not committed, licensed)

- **Fonts**: Ableton Sans Small from the user's licensed Live 12 install
  (`/Applications/Ableton Live 12 Suite.app/Contents/App-Resources/Fonts/`),
  plus Fraunces/Inter/JetBrains Mono from `~/Library/Fonts` for the page frame.
- **Chrome** at the macOS path for the headless gates.
- `reference@2x.png` is a private research fixture (a screenshot of the user's
  own Live session); it stays in this private repo only.

## Build

```sh
python3 build/assemble.py   # solver -> inline -> ratio gate -> overlap gate -> sweep -> params self-test
```

P1/P3 in ../../PLAN.md generalise this to font-parametric, CI-runnable form.
