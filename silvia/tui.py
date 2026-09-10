"""Textual projection and governance surface; core rules live in domain services."""
import asyncio
from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.widgets import Button, Footer, Header, Input, RichLog, Select, TabbedContent, TabPane, Static
from silvia.core import DomainError, ObjectiveInput, encode


class SilviaTUI(App):
    TITLE = "SilvIA"
    CSS = """
    #identity { height: auto; padding: 1; }
    Input { margin: 0 1; }
    Horizontal { height: auto; }
    Button { min-width: 10; margin: 0 1; }
    RichLog { min-height: 8; }
    #message { height: auto; color: $warning; }
    """
    BINDINGS = [("q", "quit", "Quit"), ("r", "refresh", "Refresh"), ("ctrl+p", "pause", "Pause")]

    def __init__(self, application, session_id=None):
        super().__init__()
        self.application, self.session_id, self.runner = application, session_id, None

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
                    yield RichLog(id=name, wrap=True, markup=False)
                    if name == "approvals":
                        yield Input(placeholder="Exact approval ID displayed above", id="approval-id")
                        with Horizontal():
                            yield Button("Approve", id="approve")
                            yield Button("Deny", id="deny")
                    if name == "evidence":
                        yield Input(placeholder="Artifact digest to view", id="artifact-digest")
                        yield Button("View artifact", id="artifact")
                        yield RichLog(id="artifact-content", wrap=True, markup=False)
                    if name == "memory":
                        yield Input(placeholder="Memory to remember explicitly", id="memory-input")
                        yield Button("Remember", id="remember")
        yield Footer()

    def on_mount(self):
        if self.session_id:
            self.query_one("#sessions", Select).value = self.session_id
        self.set_interval(1, self.action_refresh)
        self.action_refresh()

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
            for widget, content in (("state", {k: view[k] for k in ("work-item", "agent", "attempt", "effect")}), ("approvals", view["approval"]), ("evidence", view["evidence"]), ("memory", self.application.memory.recall(session_id=self.session_id))):
                self.query_one("#" + widget, RichLog).clear().write(encode(content))
            events = self.application.store.read(self.session_id, max(0, view["cursor"] - 100))
            self.query_one("#events", RichLog).clear().write("\n".join(f"{e['sequence']} {e['kind']} {encode(e['payload'])}" for e in events))
            self.query_one("#report", RichLog).clear().write(self.application.projections.render(self.session_id, "markdown"))
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
            elif id == "remember":
                memory = app.memory.propose(self.query_one("#memory-input", Input).value, session_id=self.session_id)
                app.memory.promote(memory["id"])
                self.query_one("#memory-input", Input).value = ""
            elif id == "artifact":
                data = app.artifacts.read(self.session_id, self.query_one("#artifact-digest", Input).value.strip())
                self.query_one("#artifact-content", RichLog).clear().write(data.decode("utf-8"))
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
