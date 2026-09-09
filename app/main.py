"""Interactive CLI entry point."""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from app.config.settings import load_settings
from app.bootstrap import Application
from app.runtime.task_manager import TaskManager
from app.safety.intervention import ConsoleInterventionGate


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-8s %(name)s: %(message)s")
    root = Path(__file__).resolve().parents[1]
    settings = load_settings()
    application = Application(root, settings, intervention=ConsoleInterventionGate())
    print("Brainless Agent starting...\n\nBrowser: READY\nChatGPT: READY\n")
    try:
        objective = input("Enter task:\n> ").strip()
        if objective:
            task = TaskManager(application.providers.names).create(objective)
            print("\n" + await application.runtime.run(task))
    finally:
        await application.close()


if __name__ == "__main__":
    asyncio.run(main())
