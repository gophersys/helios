# Develop Eden

From the host:

```bash
cd ~/code/eden
devcontainer cloud
```

Inside the container, use Nx as the public task interface:

```bash
nx check workspace
nx check change
nx check eden
nx check docs
nx run-many -t check
```

Use `nx <verb> <project> [-c <configuration>]`. Project implementations remain
private behind Nx targets.

Before changing the repository, use an isolated Git worktree on a conventional
`type/short-name` branch. `nx check change` maps every changed file to its owning
project and prints the project checks required before the broad gate. Keep
credentials outside Git and ask before deployment, release, external mutation,
or work expected to exceed ten minutes.
