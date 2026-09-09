# Brainless Agent

Brainless Agent is a Python computer-use runtime. It orchestrates a real, persistent Chrome session and uses chatbot **websites** as interchangeable reasoning engines. It does not call OpenAI, Gemini, Anthropic, or any other model reasoning API, and it has no API-key configuration.

## vNext autonomous computer-agent runtime

Alongside the existing browser-provider workflow, vNext adds a runtime-owned autonomous execution path:

```text
USER -> Root -> capability analysis -> AgentRegistry -> reuse | AgentFactory
     -> AgentSupervisor/ActionRuntime -> observe -> structured decision -> policy/permission
     -> resource lock -> controller action -> observe and verify -> audited result
```

`app/autonomy` is model independent: a decision provider can propose only a typed `ComputerAction`; it cannot access Python, the OS, controller backends, permissions, or tool registration. `ActionRuntime` validates identity, allow-listed tool, permission, global policy, arguments, locks shared resources, executes through a replaceable `ComputerController`, observes again, and verifies expected state. Failures are machine-readable (`PERMISSION_DENIED`, `CAPABILITY_UNAVAILABLE`, `VERIFICATION_FAILED`, and related codes), bounded by step and failure budgets, and logged in runtime audit records.

The production `PlaywrightComputerController` implements real browser observation/navigation and explicitly reports unsupported OS capabilities rather than faking success. OS/browser/filesystem/process adapters remain behind `ToolRegistry`; platform-specific controllers can be added without changing the agent hierarchy. The integration tests use an injected deterministic controller solely to make the full runtime flow reproducible; production actions are never hard-coded workflows.

Agents are configurations, not fixed classes. `CapabilityAnalyzer` derives conservative minimum requirements, `AgentRegistry` reuses an idle compatible agent, and `AgentFactory` validates an `AgentSpec`, parent permission boundary, and registered tool metadata before creation. Parent-owned grants remain the only way to add permissions. `ResourceLockManager` serializes mouse/keyboard/browser/screen resources. Existing `AgentManager` continues to supply hierarchy, lifecycle, pause/resume/retry/termination, parallel independent execution, and persisted event auditing.

### Autonomous runtime test coverage

`tests/test_autonomous_runtime.py` proves dynamic BrowserAgent creation, least-privilege navigation, observation/action verification, registry reuse, denied mouse control, authorized parent grant, and task requirement analysis. Browser, OS, and provider integrations still require the local platform and an owner-authenticated profile.

## Phase 1: working vertical slice

The current implementation is an end-to-end browser-driven MVP:

1. Opens a persistent, visible Chrome profile with Playwright.
2. Navigates to ChatGPT (or selects Gemini/Claude when named in a task).
3. Locates the webpage's semantic prompt element, writes and submits a rendered prompt.
4. Observes generation controls, extracts the rendered assistant response from the DOM, validates it is not empty, prints it, and stores it locally in SQLite.
5. Runs multiple named providers and asks the selected synthesis provider to compare their labelled responses.
6. Uses a logged runtime state machine, bounded response-extraction recovery, action/time budgets, and a cooperative emergency-stop latch.

The provider interface and adapters are implemented now so the runtime has no provider-specific branches. Gemini and Claude selectors are included, but their current UIs evolve frequently; verify the configured DOM selectors after logging in. The desktop GUI and bounded DOM/clipboard/OCR response-extraction fallbacks are available now. A system-wide emergency hotkey and visual-anchor discovery remain future work.

## Architecture

```text
CLI -> AgentRuntime -> State/Prompt/SQLite Memory -> Provider Registry
    -> Provider Adapter -> BrowserManager -> persistent Chrome -> chatbot website
```

### Hierarchical agents and tools

The runtime also provides a local, typed `AgentManager` for work that benefits from delegation. A root agent creates child agents with an explicit task, narrowly scoped context, permissions, and tool allow-list. Child permissions must be a subset of their parent's permissions; a tool is only invoked after the registry verifies both the allow-list and every required capability. Global policy can auto-approve, require human approval, or deny sensitive capabilities.

```text
USER -> ROOT AGENT -> AGENT MANAGER
                         |- Research child -> browser.read tool
                         |- Coding child   -> explicitly granted tools
                         `- Testing child  -> explicitly granted tools
```

Agent events record task, status, result, error, tool, and permission-denied outcomes. Independent children can run concurrently, and a parent can inspect the tree, collect results, retry bounded failures, pause, resume, or terminate direct children. The provider websites remain the reasoning layer; agent orchestration and tool permissions remain in Python.

The runtime observes after navigation and before sending input. Provider adapters use DOM/accessibility locators instead of fixed screen coordinates. If a login, CAPTCHA, 2FA, or another security challenge is detected, the run stops and tells the user to complete it manually. The project never captures passwords, exports cookies, or attempts to bypass a security mechanism.

## Installation

Requires Python 3.11+ and an installed Google Chrome/Chrome-compatible browser.

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
playwright install chromium
```

`channel: chrome` in `app/config/providers.yaml` asks Playwright for the installed Chrome channel. If Chrome is not installed, install it or change the channel to a supported locally installed browser.

## First-run Chrome setup

Run the application once, let the visible Chrome window open, and manually sign in to the service(s) you own. The profile is retained at `data/browser-profile`; it is local-only and gitignored. Do not point it at a profile that is currently open in another Chrome process. Do not put credentials in this repository.

## Run

```bash
python run.py
```

### Desktop UI

Run `python run_gui.py` to launch the Tk desktop UI. It provides a task editor, provider checkboxes, strategy and prompt-profile selectors, Start, cooperative Pause/Resume, Emergency Stop, current status, an in-window result/error log, and a refreshable local task-history table. The browser closes after each GUI run while the persistent profile remains for the next run. Pause takes effect at the next action boundary. Emergency Stop cancels the in-flight browser operation and records the failure state; it does not bypass, dismiss, or otherwise alter provider security pages.

When a provider shows login, CAPTCHA, 2FA, or another security challenge, Brainless pauses without attempting a bypass. Complete the challenge yourself, then press **Continue after login** in the GUI or Enter in the CLI; the runtime verifies the page again before it sends a prompt.

At the prompt, enter a task such as:

```text
Research resilient browser automation patterns.
```

Mentioning more than one configured provider (for example, `compare chatgpt and gemini`) activates deterministic multi-provider task parsing. In the desktop UI, selecting more than one provider also creates a multi-provider workflow when Strategy is **automatic**. The runtime collects labelled answers and sends them to its selected synthesis provider (ChatGPT when selected, otherwise the first selected provider) for a final result.

## Configuration and prompts

Provider URLs, persistent profile location, browser behavior, and bounded runtime limits are in `app/config/providers.yaml`. Prompt templates live in `prompts/<profile>/default.txt`; an optional `prompts/<profile>/<provider>.txt` overrides the default for one provider. Templates support `{task}`, `{previous_results}`, `{provider}`, `{context}`, and `{requirements}`. The runtime retrieves bounded, keyword-matched local context before the first provider prompt. The parser deterministically selects `research`, `coding`, or `analysis` today.

## Adding a provider

Create an adapter subclass of `ChatbotProvider`, give it webpage input/response/stop selectors, and add it to `ProviderRegistry.from_settings`. The agent runtime does not need to change. Test it against the provider's normal browser UI while logged into your own account.

## Local memory

Each completed or failed provider interaction is recorded in `data/memory.db` with task ID, timestamp, provider, prompt, response/status, duration, workflow, errors, and a screenshot path when capture succeeds. Existing databases are migrated in place to add screenshot metadata. `SQLiteMemory.search()` provides local keyword retrieval for later prompt context; no task content is sent to an API by this program.

## Safety and troubleshooting

* You retain control of the visible browser. Stop the process with `Ctrl+C`; the persistent browser context closes cleanly.
* Complete login, CAPTCHA, and 2FA manually. The runtime will not bypass them.
* If an input is not found, inspect the provider website after login and update the adapter selector list. Website DOMs can change.
* Browser actions are bounded by config timeouts and recovery retries; failures are recorded in SQLite.

## Roadmap

Normal response extraction is DOM-first. If its bounded recovery fails, the runtime tries the provider's visible response Copy control plus the local clipboard, then uses local OCR on a recorded screenshot. Every candidate is validated before it can be persisted. OCR requires the optional local Tesseract executable in addition to the Python dependencies.

Next phases add authenticated browser integration tests, provider-specific selector maintenance, visual-anchor discovery, a global emergency hotkey, and task-history controls in the desktop UI.

## Tests

```bash
pytest
```

These tests cover configuration, prompt rendering, local SQLite memory, state transitions, bounded recovery, provider registry behavior, and deterministic task parsing. Browser UI automation remains a manual integration test because it requires the owner's logged-in Chrome session.
