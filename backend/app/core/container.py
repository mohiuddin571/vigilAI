"""The composition root.

This is the one module in the project allowed to import across every layer
(domain, application, infrastructure, interfaces) — its entire job is to
build concrete adapters and inject them into use cases via plain constructor
arguments (TD-08: manual DI, not a framework, not FastAPI's `Depends`).

Empty in this milestone: there are no concrete infrastructure adapters yet
(those start at M2/M3), so there is nothing to wire up. Later milestones add
one `build_*` function per adapter/use case here as they're implemented.
"""


class Container:
    """Holds the wired object graph for the application's lifetime."""
