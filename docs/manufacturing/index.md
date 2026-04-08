---
min_role: OPERATOR
---
# Manufacturing

Boards come off the assembly line and go straight into a test fixture. The fixture powers the board, flashes approved firmware, and runs POST -- a series of automated checks covering power rails, sensors, connectivity, and personalization. The board either passes and goes into the shipping bin, or fails with a clear reason on screen.

This section covers the full manufacturing workflow:

- [Configuration](configuration.md) -- setting up stages, firmware source, and pass criteria (Maintainer)
- [Manufacturing fixtures](fixture.md) -- creating fixture designs and instances for the factory floor (Maintainer)
- [Sessions](sessions.md) -- starting sessions, scanning panels, watching results, ending runs (Operator)
- [Station setup](station-setup.md) -- hardware, login, and fixture prep
- [Running POST](running-post.md) -- scanning boards and running tests
- [Reading results](reading-results.md) -- interpreting outcomes and tracking production quality
