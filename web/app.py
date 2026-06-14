"""Optional web interface for the Ansible + Terraform automation container.

Provides:
  * discovery of mounted playbooks / Terraform projects / run logs
  * a WebSocket endpoint that runs a tool and streams its output live
  * a log file viewer

Nothing else in the container imports this module, so the web interface is a
strictly optional add-on — every action here is also available from the CLI.
"""
from __future__ import annotations

import asyncio
import json
import os
import shlex
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# --------------------------------------------------------------------------
# Configuration (all overridable via environment)
# --------------------------------------------------------------------------
AUTOMATION_HOME = Path(os.environ.get("AUTOMATION_HOME", "/automation"))
ANSIBLE_DIR = Path(os.environ.get("AUTOMATION_ANSIBLE_DIR", AUTOMATION_HOME / "ansible"))
TERRAFORM_DIR = Path(os.environ.get("AUTOMATION_TERRAFORM_DIR", AUTOMATION_HOME / "terraform"))
LOG_DIR = Path(os.environ.get("AUTOMATION_LOG_DIR", AUTOMATION_HOME / "logs"))
LOG_DIR.mkdir(parents=True, exist_ok=True)

BASE_DIR = Path(__file__).resolve().parent

TERRAFORM_ACTIONS = {
    "init", "validate", "plan", "apply", "destroy", "output", "refresh", "fmt", "show",
}

app = FastAPI(title="Automation Console")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def safe_join(base: Path, target: str) -> Path:
    """Join ``target`` to ``base`` ensuring the result stays inside ``base``."""
    base_resolved = base.resolve()
    candidate = (base_resolved / target).resolve()
    if candidate != base_resolved and base_resolved not in candidate.parents:
        raise ValueError("path escapes the allowed directory")
    return candidate


def secure_name(name: str) -> str:
    if "/" in name or "\\" in name or name.startswith("."):
        raise HTTPException(status_code=400, detail="invalid name")
    return name


def list_playbooks() -> list[str]:
    results: set[str] = set()
    if ANSIBLE_DIR.exists():
        candidates = list(ANSIBLE_DIR.glob("*.yml")) + list(ANSIBLE_DIR.glob("*.yaml"))
        pb_dir = ANSIBLE_DIR / "playbooks"
        if pb_dir.exists():
            candidates += list(pb_dir.rglob("*.yml")) + list(pb_dir.rglob("*.yaml"))
        for p in candidates:
            if p.name in {"requirements.yml", "ansible-requirements.yml"}:
                continue
            results.add(str(p.relative_to(ANSIBLE_DIR)))
    return sorted(results)


def list_inventories() -> list[str]:
    results: set[str] = set()
    if ANSIBLE_DIR.exists():
        for name in ("inventory", "inventories", "hosts", "hosts.ini", "inventory.ini", "inventory.yml"):
            p = ANSIBLE_DIR / name
            if p.exists():
                results.add(name)
        inv_dir = ANSIBLE_DIR / "inventory"
        if inv_dir.is_dir():
            for p in inv_dir.iterdir():
                results.add(str(p.relative_to(ANSIBLE_DIR)))
    return sorted(results)


def list_tf_projects() -> list[str]:
    results: set[str] = set()
    if TERRAFORM_DIR.exists():
        for tf in TERRAFORM_DIR.rglob("*.tf"):
            rel = tf.parent.relative_to(TERRAFORM_DIR)
            results.add(str(rel) if str(rel) != "." else ".")
    return sorted(results)


def list_logs() -> list[dict]:
    logs = []
    for p in sorted(LOG_DIR.glob("*.log"), key=lambda x: x.stat().st_mtime, reverse=True):
        st = p.stat()
        logs.append(
            {
                "name": p.name,
                "size": st.st_size,
                "modified": datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds"),
            }
        )
    return logs


def build_commands(payload: dict) -> tuple[list[list[str]], Path, str]:
    """Translate a web request into a list of commands + working dir + log label."""
    tool = payload.get("tool")

    if tool == "ansible":
        target = (payload.get("target") or "").strip()
        if not target:
            raise ValueError("no playbook selected")
        playbook = safe_join(ANSIBLE_DIR, target)
        if not playbook.is_file():
            raise ValueError(f"playbook not found: {target}")

        cmd = ["ansible-playbook", str(playbook)]

        inventory = (payload.get("inventory") or "").strip()
        if inventory:
            cmd += ["-i", str(safe_join(ANSIBLE_DIR, inventory))]
        elif (ANSIBLE_DIR / "inventory").exists():
            cmd += ["-i", str(ANSIBLE_DIR / "inventory")]

        extra_vars = (payload.get("extra_vars") or "").strip()
        if extra_vars:
            cmd += ["--extra-vars", extra_vars]

        limit = (payload.get("limit") or "").strip()
        if limit:
            cmd += ["--limit", limit]

        tags = (payload.get("tags") or "").strip()
        if tags:
            cmd += ["--tags", tags]

        if payload.get("check"):
            cmd.append("--check")
        if payload.get("verbose"):
            cmd.append("-vvv")

        cmd += shlex.split(payload.get("args") or "")
        return [cmd], ANSIBLE_DIR, "ansible"

    if tool == "terraform":
        target = (payload.get("target") or ".").strip()
        workdir = safe_join(TERRAFORM_DIR, target)
        if not workdir.is_dir():
            raise ValueError(f"terraform project not found: {target}")

        action = (payload.get("command") or "plan").strip()
        if action not in TERRAFORM_ACTIONS:
            raise ValueError(f"terraform action not allowed: {action}")

        commands: list[list[str]] = []
        # Auto-init for actions that need initialised providers/state.
        if action in {"plan", "apply", "destroy", "refresh"} and not (workdir / ".terraform").exists():
            commands.append(["terraform", "init", "-input=false"])

        cmd = ["terraform", action]
        if action in {"apply", "destroy"}:
            cmd.append("-auto-approve")
        if action in {"plan", "apply", "destroy", "refresh"}:
            cmd.append("-input=false")
            for kv in (payload.get("extra_vars") or "").split():
                if "=" in kv:
                    cmd += ["-var", kv]
        cmd += shlex.split(payload.get("args") or "")
        commands.append(cmd)

        label = "terraform-" + (target.replace("/", "-").replace(" ", "-") or "root")
        return commands, workdir, label

    raise ValueError(f"unknown tool: {tool}")


async def stream_process(cmd: list[str], cwd: Path, ws: WebSocket, logf) -> int:
    """Run one command, streaming combined output to the websocket + log file."""
    env = os.environ.copy()
    env.setdefault("PYTHONUNBUFFERED", "1")
    env.setdefault("ANSIBLE_FORCE_COLOR", "0")
    env["TF_IN_AUTOMATION"] = "1"
    env["TF_INPUT"] = "0"

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=str(cwd),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        env=env,
    )
    assert proc.stdout is not None

    async def watch_for_stop():
        """Allow the client to cancel a run by sending {"action": "stop"}."""
        try:
            while True:
                msg = await ws.receive_text()
                if json.loads(msg).get("action") == "stop":
                    if proc.returncode is None:
                        proc.terminate()
                    return
        except Exception:
            return

    stop_task = asyncio.create_task(watch_for_stop())
    try:
        async for raw in proc.stdout:
            text = raw.decode(errors="replace").rstrip("\n")
            logf.write(text + "\n")
            logf.flush()
            await ws.send_json({"type": "output", "data": text})
        return await proc.wait()
    finally:
        stop_task.cancel()
        if proc.returncode is None:
            proc.kill()


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request, "index.html")


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.get("/api/inventory")
async def api_inventory():
    return {
        "ansible_dir": str(ANSIBLE_DIR),
        "terraform_dir": str(TERRAFORM_DIR),
        "log_dir": str(LOG_DIR),
        "playbooks": list_playbooks(),
        "inventories": list_inventories(),
        "terraform_projects": list_tf_projects(),
        "terraform_actions": sorted(TERRAFORM_ACTIONS),
    }


@app.get("/api/logs")
async def api_logs():
    return {"logs": list_logs()}


@app.get("/api/logs/{name}", response_class=PlainTextResponse)
async def api_log_content(name: str):
    name = secure_name(name)
    base = LOG_DIR.resolve()
    # resolve() follows symlinks, so a symlinked log pointing outside LOG_DIR
    # resolves to a path whose parent is no longer base and is rejected.
    path = (base / name).resolve()
    if base not in path.parents or not path.is_file():
        raise HTTPException(status_code=404, detail="log not found")
    return path.read_text(errors="replace")


@app.websocket("/ws/run")
async def ws_run(ws: WebSocket):
    await ws.accept()
    try:
        payload = json.loads(await ws.receive_text())
        commands, cwd, label = build_commands(payload)
    except WebSocketDisconnect:
        return
    except Exception as exc:  # noqa: BLE001 - report any validation error to the client
        await ws.send_json({"type": "error", "data": str(exc)})
        await ws.close()
        return

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_path = LOG_DIR / f"{ts}-{label}.log"
    pretty = " && ".join(shlex.join(c) for c in commands)
    await ws.send_json({"type": "start", "data": pretty, "log": log_path.name})

    rc = 0
    try:
        with log_path.open("w") as logf:
            logf.write(f"# started: {datetime.now().isoformat()}\n")
            logf.write(f"# workdir: {cwd}\n")
            for cmd in commands:
                header = "$ " + shlex.join(cmd)
                logf.write(header + "\n")
                await ws.send_json({"type": "output", "data": header})
                rc = await stream_process(cmd, cwd, ws, logf)
                if rc != 0:
                    break
            logf.write(f"# exited: {rc}\n")
    except WebSocketDisconnect:
        return
    except Exception as exc:  # noqa: BLE001
        await ws.send_json({"type": "error", "data": str(exc)})
        await ws.close()
        return

    await ws.send_json({"type": "end", "returncode": rc, "log": log_path.name})
    await ws.close()
