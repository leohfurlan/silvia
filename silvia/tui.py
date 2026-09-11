"""Textual projection and governance surface; core rules live in domain services."""
import asyncio
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.events import MouseDown, Paste
from textual.theme import Theme
from textual.widgets import Button, Footer, Header, Input, Select, TabbedContent, TabPane, Static, TextArea
from silvia.core import DomainError, ObjectiveInput, encode, encode_pretty


class ContextMenu(Static):
    """Minimal right-click context menu for copy/paste actions."""

    DEFAULT_CSS = """
    ContextMenu {
        background: #1a1a0a;
        border: tall #b8860b;
        width: 14;
        height: auto;
        layer: overlay;
    }
    ContextMenu Button {
        width: 100%;
        min-width: 12;
        margin: 0;
        border: none;
        background: #1a1a0a;
        color: #f5c542;
    }
    ContextMenu Button:hover {
        background: #e5a93c;
        color: #000000;
    }
    """

    def __init__(self, x: int, y: int, target) -> None:
        super().__init__()
        self._x = x
        self._y = y
        self._target = target

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Button("📋 Copy", id="ctx-copy")
            yield Button("📌 Paste", id="ctx-paste")

    def on_mount(self) -> None:
        self.offset = (self._x, self._y)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        target = self._target
        if event.button.id == "ctx-copy":
            if isinstance(target, TextArea):
                text = target.selected_text or target.text
            elif isinstance(target, Input):
                text = target.value
            else:
                text = ""
            if text:
                self.app.copy_to_clipboard(text)
                self.app.query_one("#message", Static).update("Copied to clipboard.")
        elif event.button.id == "ctx-paste":
            # Post a Paste event to the target so Textual injects clipboard content
            if hasattr(target, "post_message"):
                target.post_message(Paste(""))
        self.remove()

    def on_mouse_down(self, event: MouseDown) -> None:
        # Click outside the menu dismisses it
        if not self.region.contains(event.screen_x, event.screen_y):
            self.remove()


HERMES_THEME = Theme(
    name="hermes",
    primary="#e5a93c",       # Hermes gold / amber
    secondary="#b8860b",     # Dark goldenrod border
    accent="#f5c542",        # Bright gold highlight
    foreground="#f3c647",    # Warm yellow text
    background="#000000",    # Pitch black background
    surface="#0a0a0a",       # Deep black surface
    panel="#121212",         # Dark panel
    boost="#1a1811",         # Subtle golden-black boost
    warning="#ffb703",       # Amber warning
    error="#e63946",         # Crimson error
    success="#52b788",       # Jade green success
    dark=True,
)


class SilviaTUI(App):
    TITLE = "SilvIA"
    CSS = """
    Screen {
        background: #000000;
        color: #f3c647;
    }
    #identity {
        height: auto;
        padding: 1;
        background: #0a0a0a;
        color: #f5c542;
        border-bottom: heavy #b8860b;
    }
    Input {
        margin: 0 1;
        background: #0f0f0f;
        color: #f3c647;
        border: tall #b8860b;
    }
    Input:focus {
        border: tall #f5c542;
    }
    Select {
        background: #0f0f0f;
        color: #f3c647;
        border: tall #b8860b;
    }
    Horizontal {
        height: auto;
    }
    Button {
        min-width: 10;
        margin: 0 1;
        background: #141414;
        color: #f5c542;
        border: tall #b8860b;
    }
    Button:hover {
        background: #e5a93c;
        color: #000000;
    }
    TabbedContent {
        background: #000000;
        height: 1fr;
    }
    TabbedContent ContentSwitcher {
        height: 1fr;
    }
    TabPane {
        padding: 0;
        layout: vertical;
        height: 1fr;
    }
    TextArea {
        height: 1fr;
        background: #050505;
        color: #f3c647;
        border: tall #b8860b;
    }
    TextArea:focus {
        border: tall #f5c542;
    }
    #message {
        height: auto;
        color: #ffb703;
        padding: 0 1;
    }
    """
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("r", "refresh", "Refresh"),
        ("ctrl+p", "pause", "Pause"),
        ("t", "toggle_theme", "Toggle Theme (Hermes/Dark)"),
    ]

    def __init__(self, application, session_id=None, theme="hermes"):
        super().__init__()
        self.application, self.session_id, self.runner = application, session_id, None
        self.preferred_theme = theme or "hermes"

    def compose(self) -> ComposeResult:
        yield Header()
        yield Select([(s["name"] + " · " + s["state"], s["id"]) for s in self.application.sessions.list_sessions()], prompt="Open a session", id="sessions")
        yield Static("No session selected", id="identity")
        with Horizontal():
            yield Input(placeholder="New objective", id="objective")
            yield Input(placeholder="Observable criterion", id="criterion")
            yield Button("Create", id="create")
        with Horizontal():
            for id in ("resume", "run", "pause", "cancel", "complete"):
                yield Button(id.title(), id=id)
        yield Static("", id="message")
        with TabbedContent():
            for name in ("state", "approvals", "events", "evidence", "memory", "report"):
                with TabPane(name.title()):
                    yield TextArea(read_only=True, id=name, show_line_numbers=False)
                    if name == "approvals":
                        yield Input(placeholder="Exact approval ID displayed above", id="approval-id")
                        with Horizontal():
                            yield Button("Approve", id="approve")
                            yield Button("Deny", id="deny")
                    if name == "events":
                        with Horizontal():
                            yield Button("Copy all events", id="copy-events")
                    if name == "evidence":
                        yield Input(placeholder="Artifact digest to view", id="artifact-digest")
                        yield Button("View artifact", id="artifact")
                        yield TextArea(read_only=True, id="artifact-content", show_line_numbers=False)
                    if name == "memory":
                        yield Input(placeholder="Memory to remember explicitly", id="memory-input")
                        yield Button("Remember", id="remember")
        yield Footer()

    def on_mount(self):
        self.register_theme(HERMES_THEME)
        if self.preferred_theme == "hermes":
            self.theme = "hermes"
        if self.session_id:
            self.query_one("#sessions", Select).value = self.session_id
        self.set_interval(1, self.action_refresh)
        self.action_refresh()

    def action_toggle_theme(self):
        self.theme = "textual-dark" if self.theme == "hermes" else "hermes"
        self.query_one("#message", Static).update(f"Active theme: {self.theme}")

    def on_mouse_down(self, event: MouseDown) -> None:
        """Show context menu on right-click over TextArea or Input widgets."""
        # Dismiss any existing context menu first
        for menu in self.query(ContextMenu):
            menu.remove()
        if event.button != 3:
            return
        # Find the widget under the cursor
        # ``get_widget_at`` returns (Widget, Region); only the widget has a DOM parent.
        hit = self.get_widget_at(*event.screen_offset)
        widget = hit[0] if isinstance(hit, tuple) else hit
        if widget is None:
            return
        # Walk up the widget tree to find a TextArea or Input ancestor
        target = widget
        while target is not None and not isinstance(target, (TextArea, Input)):
            target = target.parent
        if not isinstance(target, (TextArea, Input)):
            return
        event.stop()
        menu = ContextMenu(event.screen_x, event.screen_y, target)
        self.mount(menu)

    def on_select_changed(self, event: Select.Changed):
        if event.select.id == "sessions" and event.value is not Select.BLANK:
            self.session_id = str(event.value)
            self.action_refresh()

    def action_refresh(self):
        if not self.session_id:
            return
        try:
            view = self.application.projections.snapshot(self.session_id)
            session = view["session"]
            self.query_one("#identity", Static).update(f"{session['name']} | {session['state']} | revision {session['revision']} | cursor {view['cursor']}\n{session['objective']['text']}")
            for widget, content in (
                ("state", {k: view[k] for k in ("work-item", "agent", "attempt", "effect")}),
                ("approvals", view["approval"]),
                ("evidence", view["evidence"]),
                ("memory", self.application.memory.recall(session_id=self.session_id)),
            ):
                area = self.query_one("#" + widget, TextArea)
                text = encode_pretty(content)
                if area.text != text:
                    area.load_text(text)
            events = self.application.store.read(self.session_id, max(0, view["cursor"] - 100))
            events_text = "\n".join(f"{e['sequence']} {e['kind']} {encode(e['payload'])}" for e in events)
            events_area = self.query_one("#events", TextArea)
            if events_area.text != events_text:
                events_area.load_text(events_text)
            report_text = self.application.projections.render(self.session_id, "markdown")
            report_area = self.query_one("#report", TextArea)
            if report_area.text != report_text:
                report_area.load_text(report_text)
        except DomainError as exc:
            self.query_one("#message", Static).update(f"{exc.code}: {exc.message}")

    def action_pause(self):
        if self.session_id:
            self.application.sessions.pause(self.session_id)
            self.action_refresh()

    async def on_button_pressed(self, event: Button.Pressed):
        app, id = self.application, event.button.id
        try:
            if id == "create":
                objective = self.query_one("#objective", Input).value
                criterion = self.query_one("#criterion", Input).value
                project = app.sessions.register_project(app.project)
                session = app.sessions.new_session(project["id"], objective[:80], ObjectiveInput(objective, (criterion,)))
                self.session_id = session["id"]
                select = self.query_one("#sessions", Select)
                select.set_options([(s["name"], s["id"]) for s in app.sessions.list_sessions()])
                select.value = self.session_id
            elif not self.session_id:
                raise DomainError("not-found", "Select a session first.")
            elif id == "run":
                if self.runner and not self.runner.done():
                    raise DomainError("runner-active", "Execution is already active.")
                self.runner = asyncio.create_task(self._run())
            elif id == "resume":
                result = app.sessions.resume_session(self.session_id)
                self.query_one("#message", Static).update("Reconciliation: " + encode(result) + " Review it, then press Run to confirm.")
            elif id == "pause":
                app.sessions.pause(self.session_id)
            elif id == "cancel":
                await app.cancel_session(self.session_id)
            elif id == "complete":
                app.confirm_completion(self.session_id)
            elif id in {"approve", "deny"}:
                approval = self.query_one("#approval-id", Input).value.strip()
                app.harness.grant(approval) if id == "approve" else app.harness.deny(approval, "Denied in TUI")
            elif id == "copy-events":
                events_area = self.query_one("#events", TextArea)
                self.copy_to_clipboard(events_area.text)
                self.query_one("#message", Static).update("All events copied to system clipboard!")
            elif id == "remember":
                memory = app.memory.propose(self.query_one("#memory-input", Input).value, session_id=self.session_id)
                app.memory.promote(memory["id"])
                self.query_one("#memory-input", Input).value = ""
            elif id == "artifact":
                data = app.artifacts.read(self.session_id, self.query_one("#artifact-digest", Input).value.strip())
                self.query_one("#artifact-content", TextArea).load_text(data.decode("utf-8"))
            self.action_refresh()
        except DomainError as exc:
            self.query_one("#message", Static).update(f"{exc.code}: {exc.message} {exc.suggestion}")

    async def _run(self):
        try:
            await self.application.agents.run(self.session_id)
        except DomainError as exc:
            self.query_one("#message", Static).update(f"{exc.code}: {exc.message} {exc.suggestion}")
        finally:
            self.action_refresh()

    async def action_quit(self):
        if self.runner and not self.runner.done():
            self.application.sessions.pause(self.session_id)
            await self.runner
        self.exit()
