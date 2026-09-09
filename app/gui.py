"""Tk desktop UI for starting, pausing, stopping, and reviewing Brainless tasks."""
from __future__ import annotations

import asyncio
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from app.bootstrap import Application
from app.config.settings import Settings, load_settings
from app.runtime.task_manager import TaskManager
from app.safety.intervention import UserInterventionGate


class BrainlessWindow:
    def __init__(self, root_path: Path, settings: Settings | None = None) -> None:
        self.root_path = root_path
        self.events: queue.Queue[tuple[str, str]] = queue.Queue()
        self.intervention = UserInterventionGate(lambda message: self.events.put(("intervention", message)))
        self.application = Application(root_path, settings or load_settings(), intervention=self.intervention)
        self.worker: threading.Thread | None = None
        self.window = tk.Tk()
        self.window.title("Brainless Agent")
        self.window.geometry("900x660")
        self.window.protocol("WM_DELETE_WINDOW", self.close)
        self._build()
        self._poll_events()

    def _build(self) -> None:
        frame = ttk.Frame(self.window, padding=16)
        frame.pack(fill=tk.BOTH, expand=True)
        ttk.Label(frame, text="BRainless Agent", font=("TkDefaultFont", 18, "bold")).pack(anchor=tk.W)
        ttk.Label(frame, text="Chatbot websites provide reasoning; this runtime controls the browser.").pack(anchor=tk.W, pady=(0, 12))
        ttk.Label(frame, text="Task").pack(anchor=tk.W)
        self.task = tk.Text(frame, height=7, wrap=tk.WORD)
        self.task.pack(fill=tk.X)
        provider_frame = ttk.LabelFrame(frame, text="Providers", padding=8)
        provider_frame.pack(fill=tk.X, pady=12)
        self.provider_enabled = {name: tk.BooleanVar(value=True) for name in self.application.providers.names}
        for name, variable in self.provider_enabled.items():
            ttk.Checkbutton(provider_frame, text=name.title(), variable=variable).pack(side=tk.LEFT, padx=(0, 14))
        selection_frame = ttk.Frame(frame)
        selection_frame.pack(fill=tk.X, pady=(0, 12))
        ttk.Label(selection_frame, text="Strategy").pack(side=tk.LEFT)
        self.strategy = ttk.Combobox(selection_frame, state="readonly", values=("automatic", "single", "multi"), width=14)
        self.strategy.set("automatic")
        self.strategy.pack(side=tk.LEFT, padx=(6, 18))
        ttk.Label(selection_frame, text="Prompt profile").pack(side=tk.LEFT)
        profiles = sorted(path.name for path in (self.root_path / "prompts").iterdir() if path.is_dir())
        self.prompt_profile = ttk.Combobox(selection_frame, state="readonly", values=profiles, width=16)
        self.prompt_profile.set("research")
        self.prompt_profile.pack(side=tk.LEFT, padx=6)
        controls = ttk.Frame(frame)
        controls.pack(fill=tk.X)
        self.start_button = ttk.Button(controls, text="Start Agent", command=self.start)
        self.start_button.pack(side=tk.LEFT)
        self.pause_button = ttk.Button(controls, text="Pause", command=self.toggle_pause, state=tk.DISABLED)
        self.pause_button.pack(side=tk.LEFT, padx=8)
        self.stop_button = ttk.Button(controls, text="Emergency Stop", command=self.stop, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT)
        self.continue_button = ttk.Button(controls, text="Continue after login", command=self.continue_after_intervention,
                                          state=tk.DISABLED)
        self.continue_button.pack(side=tk.LEFT, padx=8)
        self.status = tk.StringVar(value="Idle")
        ttk.Label(frame, textvariable=self.status).pack(anchor=tk.W, pady=(14, 3))
        self.log = tk.Text(frame, height=12, state=tk.DISABLED, wrap=tk.WORD)
        self.log.pack(fill=tk.BOTH, expand=True)
        history_frame = ttk.LabelFrame(frame, text="Local task history", padding=6)
        history_frame.pack(fill=tk.X, pady=(12, 0))
        self.history = ttk.Treeview(history_frame, columns=("provider", "status", "response"), show="headings", height=5)
        for column, width in (("provider", 100), ("status", 100), ("response", 620)):
            self.history.heading(column, text=column.title())
            self.history.column(column, width=width, anchor=tk.W)
        self.history.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(history_frame, text="Refresh", command=self.refresh_history).pack(side=tk.RIGHT, padx=(8, 0))
        self.refresh_history()

    def start(self) -> None:
        objective = self.task.get("1.0", tk.END).strip()
        providers = [name for name, enabled in self.provider_enabled.items() if enabled.get()]
        if not objective or not providers:
            messagebox.showwarning("Task required", "Enter a task and select at least one provider.")
            return
        task = TaskManager(self.application.providers.names).create(
            objective, providers, self.strategy.get(), self.prompt_profile.get(),
        )
        self.start_button.configure(state=tk.DISABLED)
        self.pause_button.configure(state=tk.NORMAL, text="Pause")
        self.stop_button.configure(state=tk.NORMAL)
        self.status.set("Starting browser")
        self.worker = threading.Thread(target=self._run_task, args=(task,), daemon=True)
        self.worker.start()

    def _run_task(self, task) -> None:
        async def execute() -> str:
            try:
                return await self.application.runtime.run(task)
            finally:
                # The worker owns this event loop. Close Playwright here so a later
                # Start action can safely create a fresh loop and reuse the profile.
                await self.application.browser.close()
        try:
            result = asyncio.run(execute())
            self.events.put(("complete", result))
        except Exception as error:
            self.events.put(("error", str(error)))

    def toggle_pause(self) -> None:
        pause = self.application.runtime.pause
        if pause.paused:
            pause.resume()
            self.pause_button.configure(text="Pause")
            self.status.set("Resumed")
        else:
            pause.pause()
            self.pause_button.configure(text="Resume")
            self.status.set("Paused at next action boundary")

    def stop(self) -> None:
        self.application.runtime.pause.resume()
        self.application.runtime.emergency_stop.trigger()
        self.status.set("Emergency stop requested")

    def continue_after_intervention(self) -> None:
        self.intervention.continue_run()
        self.continue_button.configure(state=tk.DISABLED)
        self.status.set("Verifying provider page")

    def _poll_events(self) -> None:
        try:
            while True:
                kind, text = self.events.get_nowait()
                if kind == "intervention":
                    self.status.set(text)
                    self.continue_button.configure(state=tk.NORMAL)
                    continue
                self._append(text)
                self.status.set("Completed" if kind == "complete" else "Failed or stopped")
                self.start_button.configure(state=tk.NORMAL)
                self.pause_button.configure(state=tk.DISABLED)
                self.stop_button.configure(state=tk.DISABLED)
                self.continue_button.configure(state=tk.DISABLED)
                self.refresh_history()
        except queue.Empty:
            pass
        self.window.after(150, self._poll_events)

    def _append(self, text: str) -> None:
        self.log.configure(state=tk.NORMAL)
        self.log.insert(tk.END, text + "\n\n")
        self.log.see(tk.END)
        self.log.configure(state=tk.DISABLED)

    def refresh_history(self) -> None:
        for item in self.history.get_children():
            self.history.delete(item)
        for record in self.application.memory.search("", limit=20):
            preview = record.response.replace("\n", " ")[:120] or (record.error or "")[:120]
            self.history.insert("", tk.END, values=(record.provider, record.status, preview))

    def close(self) -> None:
        self.stop()
        self.window.destroy()

    def run(self) -> None:
        self.window.mainloop()


def main() -> None:
    root_path = Path(__file__).resolve().parents[1]
    BrainlessWindow(root_path).run()


if __name__ == "__main__":
    main()
