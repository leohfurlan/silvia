"""Scriptable commands and interactive shell over the application API."""
from __future__ import annotations
import argparse
import asyncio
import json
import shlex
import sqlite3
import sys
from pathlib import Path
from silvia import __version__
from silvia.application import Application
from silvia.config import config_home
from silvia.core import DomainError, ObjectiveInput, encode
from silvia.git import fingerprint
from silvia.reports import ProjectionEngine


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise DomainError("usage", message, "Run silvia --help or the command's --help.")


def parser():
    root = Parser(prog="silvia", description="Local-first, governed software development with persistent sessions.")
    root.add_argument("--version", action="version", version="SilvIA " + __version__)
    root.add_argument("--json", action="store_true", help="Emit one machine-readable JSON document")
    root.add_argument("--home", type=Path, help="Isolated storage directory; also SILVIA_HOME")
    root.add_argument("--project", type=Path, default=Path.cwd())
    sub = root.add_subparsers(dest="command", parser_class=Parser)
    init = sub.add_parser("init", help="Register a stable project identity")
    init.add_argument("--project-id")
    session = sub.add_parser("session", help="Manage sessions and objective revisions")
    commands = session.add_subparsers(dest="operation", required=True, parser_class=Parser)
    _new_options(commands.add_parser("new", help="Create a session and isolated checkout"))
    commands.add_parser("list")
    for name in ("show", "resume", "archive"):
        commands.add_parser(name).add_argument("id", nargs="?")
    revise = commands.add_parser("revise")
    revise.add_argument("id")
    revise.add_argument("objective")
    revise.add_argument("--criterion", action="append", required=True)
    revise.add_argument("--expected-revision", type=int, required=True)
    plan = commands.add_parser("plan", help="Propose a task graph from JSON")
    plan.add_argument("file", type=Path)
    plan.add_argument("--session")
    plan.add_argument("--source", action="append", default=[])
    propose = commands.add_parser("propose", help="Ask the configured orchestrator for a plan")
    propose.add_argument("--session")
    propose.add_argument("--profile", default="astra")
    reconcile = commands.add_parser("reconcile")
    reconcile.add_argument("record_id")
    reconcile.add_argument("--session")
    reconcile.add_argument("--resolution", choices=["not-executed", "completed", "abandoned"], required=True)
    reconcile.add_argument("--reason", required=True)
    for name in ("run", "status", "inspect", "resume", "pause", "cancel", "complete", "events", "gates", "agents", "approvals"):
        sub.add_parser(name).add_argument("id", nargs="?")
    _new_options(sub.add_parser("new", help="Alias for session new"))
    sub.add_parser("sessions", help="Alias for session list")
    for name in ("approve", "deny"):
        cmd = sub.add_parser(name, help=f"{name.title()} one exact pending request")
        cmd.add_argument("id")
        cmd.add_argument("--reason", default="user decision")
        if name == "approve":
            cmd.add_argument("--seconds", type=int, default=900)
            cmd.add_argument("--scope", choices=["invocation", "work-item", "session"], default="invocation")
    report = sub.add_parser("report", help="Render a deterministic report")
    report.add_argument("id", nargs="?")
    report.add_argument("--format", choices=["json", "markdown", "jsonl"], default="markdown")
    report.add_argument("--output", type=Path)
    export = sub.add_parser("export", help="Export after scoped authorization")
    export.add_argument("destination", type=Path)
    export.add_argument("--session")
    sub.add_parser("verify", help="Verify an export without extracting it").add_argument("file", type=Path)
    memory = sub.add_parser("memory", help="Manage contextual memory")
    mem = memory.add_subparsers(dest="operation", required=True, parser_class=Parser)
    remember = mem.add_parser("remember")
    remember.add_argument("content")
    remember.add_argument("--session")
    remember.add_argument("--scope", choices=["session", "project", "user"], default="session")
    remember.add_argument("--type", choices=["fact", "decision", "preference", "learning"], default="fact")
    remember.add_argument("--key")
    remember.add_argument("--candidate", action="store_true")
    for name in ("recall", "export", "retention"):
        cmd = mem.add_parser(name)
        cmd.add_argument("--session")
        if name == "recall":
            cmd.add_argument("query", nargs="?", default="")
            cmd.add_argument("--budget", type=int, default=4000)
        if name == "retention":
            cmd.add_argument("--days", type=int, default=90)
    for name in ("forget", "promote"):
        cmd = mem.add_parser(name)
        cmd.add_argument("id")
        cmd.add_argument("--session")
    skills = sub.add_parser("skills", help="Inspect explicitly registered local skills")
    skill = skills.add_subparsers(dest="operation", required=True, parser_class=Parser)
    register = skill.add_parser("register")
    register.add_argument("name")
    register.add_argument("path", type=Path)
    skill.add_parser("sources")
    for name in ("list", "show", "validate"):
        cmd = skill.add_parser(name)
        cmd.add_argument("source")
        if name != "list":
            cmd.add_argument("path")
    run_skill = skill.add_parser("run", help="Run a declared capability through the configured sandbox")
    run_skill.add_argument("source")
    run_skill.add_argument("path")
    run_skill.add_argument("capability")
    run_skill.add_argument("--session")
    for name in ("tui", "watch"):
        sub.add_parser(name, help="Open session governance TUI").add_argument("id", nargs="?")
    sub.add_parser("doctor", help="Inspect local capabilities without provider calls")
    sub.add_parser("storage").add_argument("operation", choices=["migrate"])
    sub.add_parser("config").add_argument("operation", choices=["paths", "example"], nargs="?", default="paths")
    artifact = sub.add_parser("artifact", help="Read a verified artifact")
    artifact.add_argument("digest")
    artifact.add_argument("--session")
    return root


def _new_options(cmd):
    cmd.add_argument("objective")
    cmd.add_argument("--criterion", action="append", required=True, help="Observable acceptance criterion; repeatable")
    cmd.add_argument("--constraint", action="append", default=[])
    cmd.add_argument("--name")
    cmd.add_argument("--direct", action="store_true", help="Explicitly use this checkout instead of a Git worktree")


def normalize_args(argv):
    globals, rest, i = [], [], 0
    while i < len(argv):
        if argv[i] == "--json":
            globals.append(argv[i])
        elif argv[i] in {"--home", "--project"} and i + 1 < len(argv):
            globals.extend(argv[i:i+2])
            i += 1
        else:
            rest.append(argv[i])
        i += 1
    return globals + rest


def dispatch(app, args):
    command = args.command
    if command == "init":
        return app.sessions.register_project(args.project, project_id=args.project_id)
    if command in {"new", "session"} and (command == "new" or args.operation == "new"):
        project = app.sessions.register_project(args.project)
        return app.sessions.new_session(project["id"], args.name or args.objective[:80], ObjectiveInput(args.objective, tuple(args.criterion), tuple(args.constraint)), "direct" if args.direct else "worktree")
    if command == "sessions" or command == "session" and args.operation == "list":
        return app.sessions.list_sessions()
    if command == "session":
        operation = args.operation
        id = app.session_id(getattr(args, "id", None) or getattr(args, "session", None))
        if operation == "show":
            return app.projections.snapshot(id)
        if operation == "resume":
            return app.sessions.resume_session(id)
        if operation == "revise":
            return app.sessions.revise_objective(id, args.expected_revision, ObjectiveInput(args.objective, tuple(args.criterion)))
        if operation == "archive":
            return app.sessions.transition(id, app.sessions.inspect_session(id)["state"], "archived", "user archived")
        if operation == "plan":
            value = json.loads(args.file.read_text(encoding="utf-8"))
            return app.agents.propose_plan(id, value["items"] if isinstance(value, dict) else value, sources=args.source)
        if operation == "propose":
            return asyncio.run(app.agents.plan(id, args.profile))
        return app.sessions.reconcile(id, args.record_id, args.resolution, args.reason)
    if command == "approve":
        return app.harness.grant(args.id, scope=args.scope, seconds=args.seconds)
    if command == "deny":
        return app.harness.deny(args.id, args.reason)
    if command == "memory":
        id = app.session_id(args.session)
        if args.operation == "remember":
            value = app.memory.propose(args.content, session_id=id, scope=args.scope, type=args.type, key=args.key)
            return value if args.candidate else app.memory.promote(value["id"])
        if args.operation == "recall":
            return app.memory.recall(session_id=id, query=args.query, budget=args.budget)
        if args.operation == "promote":
            return app.memory.promote(args.id)
        if args.operation == "forget":
            return app.memory.forget(args.id, session_id=id)
        if args.operation == "retention":
            return app.memory.apply_retention(session_id=id, days=args.days)
        return app.memory.export(id)
    if command == "skills":
        if args.operation == "register":
            return app.skills.register_source(args.path, args.name)
        if args.operation == "sources":
            return app.store.all("SELECT * FROM sources ORDER BY name")
        if args.operation == "list":
            return app.skills.discover(args.source)
        if args.operation == "show":
            return app.skills.resolve(args.source, args.path)
        if args.operation == "run":
            return asyncio.run(app.agents.execute_skill_capability(app.session_id(args.session), args.source, args.path, args.capability))
        return app.skills.validate(args.source, args.path)
    if command == "doctor":
        return {"version": __version__, "data_home": str(app.home), "config_home": str(config_home()), "sqlite": sqlite3.sqlite_version, "fts5": True, "providers": app.agents.available_routes(), "offline_operations": True}
    if command == "storage":
        return {"schema_version": 1, "status": "current"}
    if command == "config":
        if args.operation == "paths":
            return {"user": str(config_home() / "config.toml"), "project": str(args.project / ".silvia/config.toml")}
        return '[providers.default]\nendpoint = "http://127.0.0.1:11434/v1"\nmodel = "YOUR_INSTALLED_MODEL"\nadapter = "openai-compatible"\ncost_policy = "local"\n# Remote credentials: credential_ref = "keyring:provider-name"\n'
    if command == "export":
        return app.projections.export_session(app.session_id(args.session), args.destination)
    if command == "artifact":
        return app.artifacts.read(app.session_id(args.session), args.digest).decode("utf-8")
    id = app.session_id(getattr(args, "id", None))
    if command in {"status", "inspect"}:
        return app.projections.snapshot(id)
    if command == "resume":
        return app.sessions.resume_session(id)
    if command == "run":
        return asyncio.run(app.agents.run(id))
    if command == "pause":
        return app.sessions.pause(id)
    if command == "cancel":
        return asyncio.run(app.cancel_session(id))
    if command == "complete":
        return app.confirm_completion(id)
    if command == "events":
        return app.projections.events(id)
    if command in {"approvals", "agents"}:
        return app.store.records("approval" if command == "approvals" else "agent", id)
    if command == "gates":
        session = app.sessions.inspect_session(id)
        return app.harness.assess_completion(session, fingerprint(Path(session["checkout"])))
    if command == "report":
        content = app.projections.render(id, args.format)
        if args.output:
            with args.output.open("x", encoding="utf-8") as stream:
                stream.write(content)
            return {"path": str(args.output.resolve()), "format": args.format}
        return json.loads(content) if args.format == "json" else content
    raise DomainError("usage", "Unknown operation.")


def display(value, json_mode=False):
    if json_mode:
        print(encode(value))
    elif isinstance(value, str):
        print(value, end="" if value.endswith("\n") else "\n")
    else:
        from rich.console import Console
        Console(highlight=False).print_json(encode(value))


def interactive(args):
    print("SilvIA — commands, /help, /tui, /quit. Start with new TEXT --criterion CRITERION.")
    while True:
        try:
            text = input("silvia> ").strip()
        except (EOFError, KeyboardInterrupt):
            return 0
        if text in {"quit", "exit", "/quit"}:
            return 0
        if not text:
            continue
        if text == "/help":
            parser().print_help()
            continue
        try:
            argv = shlex.split(text.removeprefix("/"))
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            continue
        prefix = ["--project", str(args.project)] + (["--home", str(args.home)] if args.home else [])
        main(prefix + argv)


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    argv = normalize_args(list(sys.argv[1:] if argv is None else argv))
    json_mode, app = "--json" in argv, None
    try:
        args = parser().parse_args(argv)
        if not args.command:
            if not sys.stdin.isatty() or args.json:
                display({"application": "silvia", "hint": "Use --help for commands."}, True) if args.json else parser().print_help()
                return 0
            return interactive(args)
        if args.command == "verify":
            display(ProjectionEngine.verify_import(args.file), args.json)
            return 0
        app = Application(home=args.home, project=args.project, migrate=args.command == "storage")
        if args.command in {"tui", "watch"}:
            if args.json or not sys.stdin.isatty():
                raise DomainError("tty-required", "TUI requires an interactive terminal.", "Use status --json for scripting.")
            from silvia.tui import SilviaTUI
            SilviaTUI(app, args.id).run()
            return 0
        display(dispatch(app, args), args.json)
        return 0
    except DomainError as exc:
        value = {"error": exc.as_dict()}
        if app:
            value = app.store.redactor.clean(value)
        if json_mode:
            display(value, True)
        else:
            print(f"{exc.code}: {value['error']['message']}\n{value['error']['suggestion']}", file=sys.stderr)
        return 2 if exc.code in {"usage", "validation", "invalid-objective"} else 4 if exc.code.startswith("integrity") else 3 if exc.code in {"require-approval", "require-evidence", "authorization", "reconciliation-required"} else 1
    except (OSError, ValueError, sqlite3.Error):
        display({"error": {"code": "local-error", "message": "Local operation failed.", "suggestion": "Check paths, permissions and input format."}}, json_mode)
        return 1
    except KeyboardInterrupt:
        if json_mode:
            display({"error": {"code": "cancelled", "message": "Interrupted; inspect and resume to reconcile."}}, True)
        return 130
    finally:
        if app:
            app.close()


def legacy_main():
    print("bai-workflow is deprecated; use silvia. Execution requires an approved persistent plan.", file=sys.stderr)
    argv = list(sys.argv[1:])
    if "--repo" in argv:
        argv[argv.index("--repo")] = "--project"
    if "--resume" in argv:
        index = argv.index("--resume")
        id = argv[index + 1]
        argv[index:index + 2] = []
        return main(["resume", id, *argv])
    if argv and not argv[0].startswith("-") and argv[0] not in {"session", "new", "run", "status", "doctor"}:
        # Legacy positional goals become a durable proposal, never an unapproved run.
        objective = argv.pop(0)
        checks = []
        while "--check" in argv:
            index = argv.index("--check")
            checks.append(argv[index + 1])
            argv[index:index + 2] = []
        if not checks:
            print("Supply --check as an acceptance criterion, or use silvia new --criterion.", file=sys.stderr)
            return 2
        return main(["new", objective, "--criterion", "Configured checks pass: " + "; ".join(checks), *argv])
    return main(argv)
