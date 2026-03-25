"""Build worker entry point."""

from src.config import BuildConfig
from src.worker import BuildWorker


def main():
    config = BuildConfig.from_env()
    worker = BuildWorker(config)
    worker.run()


if __name__ == "__main__":
    main()
