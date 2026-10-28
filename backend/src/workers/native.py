"""Run ARQ on Windows' Proactor loop without Unix add_signal_handler.

Keeping ProactorEventLoop is important: the pipeline needs async subprocesses.
SIGINT is handled by Python; the launcher handles stopping owned processes.
"""

import argparse
import os

from arq.worker import Worker, get_kwargs, run_worker


class WindowsWorker(Worker):
    def _add_signal_handler(self, signum, handler):
        # asyncio's Windows loop does not implement Unix signal registration.
        # Leave handle_signals=True: ARQ's False cleanup uses SIGUSR1, which
        # Windows also lacks. Python delivers console Ctrl+C normally.
        pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ai", action="store_true")
    args = parser.parse_args()
    if args.ai:
        from .ai_worker import AIWorkerSettings as Settings
    else:
        from .tasks import WorkerSettings as Settings
    if os.name == "nt":
        WindowsWorker(**get_kwargs(Settings)).run()
    else:
        run_worker(Settings)


if __name__ == "__main__":
    main()
