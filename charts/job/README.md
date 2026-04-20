# charts/job

One-shot Kubernetes Job. Typical use: database migrations, bootstrap
seeding, one-time backfills.

Status: stub.

TODO: implement. Required knobs: backoffLimit, ttlSecondsAfterFinished,
restartPolicy (Never by default), resources, env/envFromSecret contract.
