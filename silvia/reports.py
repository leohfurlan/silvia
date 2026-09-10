"""Deterministic projections and portable, untrusted export verification."""
from __future__ import annotations

import json
import re
import stat
import zipfile
from pathlib import Path, PurePosixPath, PureWindowsPath

from silvia.core import ActionRequest, DomainError, digest, encode


class ProjectionEngine:
    def __init__(self, store, sessions, artifacts, harness):
        self.store, self.sessions, self.artifacts, self.harness = store, sessions, artifacts, harness

    def snapshot(self, session_id: str) -> dict:
        with self.store.transaction():
            session = self.sessions.inspect_session(session_id)
            revisions = self.store.all("SELECT revision,data,created_at FROM objectives WHERE session_id=? ORDER BY revision", (session_id,))
            return {"schema_version": 1, "session": session, "cursor": session["cursor"], "revisions": [{**r, "data": json.loads(r["data"])} for r in revisions],
                    **{kind: self.store.records(kind, session_id) for kind in ("plan", "work-item", "agent", "attempt", "approval", "grant", "authorization-use", "effect", "evidence", "context", "artifact")}}

    def events(self, session_id: str) -> list[dict]:
        values, cursor = [], 0
        while True:
            page = self.store.read(session_id, cursor)
            values.extend(page)
            if not page:
                return values
            cursor = page[-1]["sequence"]

    @classmethod
    def _portable_value(cls, value):
        if isinstance(value, dict):
            return {key: cls._portable_value(item) for key, item in value.items() if key not in {"checkout", "location", "root", "destination"}}
        if isinstance(value, list):
            return [cls._portable_value(item) for item in value]
        if isinstance(value, str):
            if PurePosixPath(value).is_absolute() or PureWindowsPath(value).is_absolute() or value.casefold().startswith("file:"):
                return "[local-path-redacted]"
            value = re.sub(r"(?i)file:/+[^\s\"']+", "[local-path-redacted]", value)
            value = re.sub(r"(?i)[a-z]:[\\/][^\s\"']+", "[local-path-redacted]", value)
        return value

    @classmethod
    def _portable_snapshot(cls, snapshot: dict) -> dict:
        portable = cls._portable_value(json.loads(encode(snapshot)))
        baseline = portable["session"].get("baseline", {})
        portable["session"]["baseline"] = {key: baseline[key] for key in ("head", "fingerprint") if key in baseline}
        return portable
    def render(self, session_id: str, format: str = "json") -> str:
        view = self.snapshot(session_id)
        if format == "json":
            return encode(view) + "\n"
        if format == "jsonl":
            return "".join(encode(e) + "\n" for e in self.events(session_id))
        if format != "markdown":
            raise DomainError("validation", "Report format must be json, markdown or jsonl.")
        session = view["session"]
        lines = ["# SilvIA session report", "", f"Session: {session_id}", f"State: {session['state']}", f"Objective revision: {session['revision']}", f"Event cursor: {view['cursor']}", "", "## Objective", "", session["objective"]["text"], "", "## Acceptance criteria", ""]
        lines += ["- " + c for c in session["objective"]["criteria"]]
        for section in ("revisions", "plan", "work-item", "agent", "attempt", "approval", "grant", "evidence", "effect"):
            lines += ["", "## " + section, "", "```json", json.dumps(view[section], indent=2, ensure_ascii=False), "```"]
        lines += ["", "## Memory and skills supplied", ""]
        for context in view["context"]:
            lines.append(encode({"context_id": context["id"], "digest": context["digest"], "memory_ids": [m["id"] for m in context["memories"]], "skills": [s["identity"] for s in context["skills"]["items"]]}))
        usage = [e["payload"] for e in self.events(session_id) if e["kind"] == "agent.usage"]
        lines += ["", "## Provider usage", "", "```json", json.dumps(usage, indent=2), "```", "", "Costs are provider-reported or explicitly labelled estimates; missing billing data is not zero cost."]
        return "\n".join(lines) + "\n"

    def build_report(self, session_id: str, format: str = "markdown") -> dict:
        content = self.render(session_id, format)
        return self.artifacts.store_artifact(session_id, content, {"markdown": "text/markdown", "json": "application/json", "jsonl": "application/x-ndjson"}[format])

    def export_session(self, session_id: str, destination: Path) -> dict:
        session = self.sessions.inspect_session(session_id)
        destination = destination.expanduser().resolve()
        if destination.exists():
            raise DomainError("destination-exists", "Export destination already exists.", "Choose a new filename; SilvIA will not overwrite it.")
        self.harness.authorize(ActionRequest("session.export", session_id, session["revision"], str(destination)))
        with self.store.transaction():
            snapshot = self._portable_snapshot(self.snapshot(session_id))
            events = [self._portable_value(event) for event in self.events(session_id)]
            files = {"state.json": (encode(snapshot) + "\n").encode(), "events.jsonl": "".join(encode(e) + "\n" for e in events).encode()}
            for ref in snapshot["artifact"]:
                files["artifacts/" + ref["digest"]] = self.artifacts.read(session_id, ref["digest"])
            # A final scan uses all known in-memory secrets, including freshly resolved credentials.
            for name, data in files.items():
                if self.store.redactor.text(data.decode("utf-8")) != data.decode("utf-8"):
                    raise DomainError("secret-detected", "Export contains newly detected sensitive content.", "Resolve the sensitive stored artifact before exporting.")
            manifest = {"schema_version": 1, "session_id": session_id, "cursor": snapshot["cursor"], "files": {name: {"digest": digest(data), "size": len(data)} for name, data in sorted(files.items())}}
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("xb") as stream:
            with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
                for name, data in {"manifest.json": encode(manifest).encode(), **files}.items():
                    info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
                    archive.writestr(info, data)
        with self.store.transaction():
            self.store.append(session_id, "session.exported", {"manifest_digest": digest(encode(manifest)), "cursor": snapshot["cursor"]}, actor="user")
        return {"path": str(destination), "manifest": manifest, "verification": self.verify_import(destination)}

    @staticmethod
    def verify_import(path: Path) -> dict:
        try:
            with zipfile.ZipFile(path) as archive:
                entries = archive.infolist()
                names = [i.filename for i in entries]
                if len(names) > 10000 or len(set(names)) != len(names) or sum(i.file_size for i in entries) > 256 * 1024 * 1024:
                    raise ValueError("Duplicate entries or export size limit exceeded")
                for entry in entries:
                    p = PurePosixPath(entry.filename)
                    mode = entry.external_attr >> 16
                    if p.is_absolute() or ".." in p.parts or "\\" in entry.filename or ":" in entry.filename or stat.S_ISLNK(mode) or entry.is_dir():
                        raise ValueError("Unsafe archive entry")
                manifest = json.loads(archive.read("manifest.json"))
                if manifest["schema_version"] != 1:
                    raise DomainError("incompatible-export", "Export schema is not supported.")
                if set(names) != {"manifest.json", *manifest["files"]}:
                    raise ValueError("Manifest membership mismatch")
                for name, metadata in manifest["files"].items():
                    data = archive.read(name)
                    if len(data) != metadata["size"] or digest(data) != metadata["digest"]:
                        raise ValueError("Digest or size mismatch")
                    if name.startswith("artifacts/") and name != "artifacts/" + digest(data):
                        raise ValueError("Artifact address mismatch")
                state = json.loads(archive.read("state.json"))
                events = [json.loads(line) for line in archive.read("events.jsonl").splitlines()]
                if state["schema_version"] != 1 or state["session"]["id"] != manifest["session_id"] or state["cursor"] != manifest["cursor"]:
                    raise ValueError("Session metadata mismatch")
                seen = set()
                for sequence, event in enumerate(events, 1):
                    if event["schema_version"] != 1 or event["sequence"] != sequence or event["session_id"] != manifest["session_id"] or event["event_id"] in seen:
                        raise ValueError("Event sequence or identity mismatch")
                    if event.get("causation_id") and event["causation_id"] not in seen:
                        raise ValueError("Missing causal event")
                    seen.add(event["event_id"])
                if len(events) != manifest["cursor"]:
                    raise ValueError("Event cursor mismatch")
                for ref in state["artifact"]:
                    if "artifacts/" + ref["digest"] not in manifest["files"]:
                        raise ValueError("Missing referenced artifact")
                return {"valid": True, "session_id": manifest["session_id"], "events": len(events), "files": len(names), "mutated": False}
        except DomainError:
            raise
        except (OSError, zipfile.BadZipFile, ValueError, KeyError, TypeError, RuntimeError) as exc:
            raise DomainError("integrity-failed", "Export failed integrity verification.", "Use an intact export; no content was extracted or executed.") from exc
