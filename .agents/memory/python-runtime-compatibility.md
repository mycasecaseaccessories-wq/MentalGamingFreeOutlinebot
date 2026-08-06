---
name: Python runtime compatibility
description: Imported workspace dependency metadata must stay compatible with the configured Replit Python runtime.
---

The configured Replit runtime for this project is Python 3.12, so root dependency metadata must not require Python 3.13 or newer unless the runtime is explicitly upgraded.

**Why:** Dependency synchronization refuses to resolve when the project metadata requires a newer interpreter than the managed runtime, even if the bot's own requirements support Python 3.12.

**How to apply:** Check `requires-python` and pinned dependency versions before syncing packages or changing the bot workflow.