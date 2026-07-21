# /// script
# requires-python = ">=3.9"
# dependencies = ["textual>=1.0"]
# ///
# claude-packs-tui — the rich, GUI-feel interactive UI for claude-packs.
#
# Launched by `bin/claude-packs` (the `tui` command) when a Python runtime with
# Textual is available — directly, or via `uv run` using the inline metadata
# above. The bash CLI stays the single source of truth for install/uninstall/
# update logic: this UI reads manifests + receipts for display and shells out
# to the CLI for every action.
#
# Environment contract (set by the launcher; sensible fallbacks for dev runs):
#   CLAUDE_PACKS_ROOT         registry root (contains bundles/)
#   CLAUDE_PACKS_CLI          path to the bash CLI to shell out to
#   CLAUDE_PACKS_VERSION      CLI version string, shown in the header
#   CLAUDE_PACKS_TARGET_MODE  initial target: "user" or "project"
#   CLAUDE_PACKS_PROJECT_DIR  initial project dir when mode is "project"

import asyncio
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Set, Tuple

from rich.table import Table
from rich.text import Text
from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen, Screen
from textual.widgets import (
    Button,
    Footer,
    Input,
    Label,
    ListItem,
    ListView,
    RadioButton,
    RadioSet,
    SelectionList,
    Static,
)

REPO_FALLBACK = Path(__file__).resolve().parent.parent
ROOT = Path(os.environ.get("CLAUDE_PACKS_ROOT") or REPO_FALLBACK)
CLI = os.environ.get("CLAUDE_PACKS_CLI") or str(REPO_FALLBACK / "bin" / "claude-packs")
VERSION = os.environ.get("CLAUDE_PACKS_VERSION", "")
RECEIPT = ".claude-packs"


# --- data layer -----------------------------------------------------------------

@dataclass
class Bundle:
    name: str
    version: str
    title: str
    description: str
    skills: List[str] = field(default_factory=list)
    agents: List[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.skills) + len(self.agents)


@dataclass
class Target:
    mode: str = "user"          # "user" | "project"
    project_dir: str = "."

    @property
    def path(self) -> Path:
        if self.mode == "project":
            return Path(self.project_dir).resolve() / ".claude"
        return Path.home() / ".claude"

    @property
    def pretty(self) -> str:
        p = str(self.path)
        home = str(Path.home())
        if p == home + "/.claude":
            return "~/.claude  (user — all projects)"
        return p.replace(home, "~", 1) if p.startswith(home) else p

    def cli_flags(self) -> List[str]:
        if self.mode == "project":
            return ["--project", str(Path(self.project_dir).resolve())]
        return ["--user"]


def load_bundles() -> List[Bundle]:
    out: List[Bundle] = []
    bdir = ROOT / "bundles"
    if not bdir.is_dir():
        return out
    for d in sorted(bdir.iterdir()):
        m = d / "bundle.json"
        if not m.is_file():
            continue
        try:
            data = json.loads(m.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        out.append(
            Bundle(
                name=d.name,
                version=str(data.get("version") or "0.0.0"),
                title=str(data.get("title") or ""),
                description=str(data.get("description") or ""),
                skills=[str(s) for s in data.get("skills") or []],
                agents=[str(a) for a in data.get("agents") or []],
            )
        )
    return out


def receipt_read(target: Path, bundle: str) -> Tuple[str, Set[Tuple[str, str]]]:
    """-> (installed version or '', {(kind, item), ...}) for one bundle."""
    version, items = "", set()
    f = target / RECEIPT
    try:
        lines = f.read_text().splitlines()
    except OSError:
        return version, items
    for line in lines:
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 4 or parts[0] != bundle:
            continue
        if not version:
            version = parts[1]
        if parts[2] in ("skill", "agent"):
            items.add((parts[2], parts[3]))
    return version, items


def status_text(b: Bundle, target: Path) -> Text:
    inst_ver, items = receipt_read(target, b.name)
    n = len(items)
    t = Text()
    if n == 0:
        t.append("○ not installed", style="dim")
    elif n < b.total:
        t.append(f"◑ partial ({n}/{b.total})", style="yellow")
    else:
        t.append("● installed", style="green")
    if inst_ver and inst_ver != b.version:
        t.append(f"  {inst_ver} → {b.version} available", style="dim italic")
    return t


async def run_cli(*args: str) -> Tuple[int, str]:
    """Run the bash CLI non-interactively, capturing combined output."""
    env = dict(os.environ, NO_COLOR="1")
    proc = await asyncio.create_subprocess_exec(
        CLI,
        *args,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        env=env,
    )
    out_b, _ = await proc.communicate()
    return proc.returncode or 0, out_b.decode(errors="replace").strip()


# --- modal dialogs ---------------------------------------------------------------

PROVIDERS = [
    ("claude", "Claude Code", "skills + agents in .claude/"),
    ("copilot", "GitHub Copilot", "prompts + agents in .github/"),
    ("cursor", "Cursor", "commands + rules in .cursor/"),
]


class TargetPicker(ModalScreen[Optional[Tuple[Target, List[str]]]]):
    """'Where to?' dialog: target folder — and, when installing, which
    AI assistants (providers) to install the files for."""

    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    def __init__(self, heading: str, current: Target,
                 ask_providers: bool = False) -> None:
        super().__init__()
        self.heading = heading
        self.current = current
        self.ask_providers = ask_providers

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label(self.heading, id="dialog-title")
            if self.ask_providers:
                yield Label("For which AI assistants?", classes="dialog-section")
                yield SelectionList(
                    *[
                        (Text.assemble((label, "bold"), ("   " + hint, "dim")),
                         key, key == "claude")
                        for key, label, hint in PROVIDERS
                    ],
                    id="providers",
                )
                yield Label("Install where?", classes="dialog-section")
            with RadioSet(id="target-choice"):
                yield RadioButton(
                    "User — ~/.claude  (available in every project)",
                    value=self.current.mode == "user",
                    id="opt-user",
                )
                yield RadioButton(
                    f"This project — {Path.cwd()}",
                    value=self.current.mode == "project",
                    id="opt-project",
                )
                yield RadioButton("Another folder…", id="opt-custom")
            yield Input(
                placeholder="path to a project folder (~ works)",
                id="custom-path",
                classes="hidden",
            )
            yield Label("", id="dialog-error")
            with Horizontal(classes="buttons"):
                yield Button("OK", variant="primary", id="ok")
                yield Button("Cancel", id="cancel")

    @on(RadioSet.Changed, "#target-choice")
    def _toggle_input(self, event: RadioSet.Changed) -> None:
        box = self.query_one("#custom-path", Input)
        custom = event.pressed.id == "opt-custom"
        box.set_class(not custom, "hidden")
        if custom:
            box.focus()

    @on(Input.Submitted, "#custom-path")
    def _submit_path(self) -> None:
        self._confirm()

    @on(Button.Pressed, "#ok")
    def _ok(self) -> None:
        self._confirm()

    @on(Button.Pressed, "#cancel")
    def action_cancel(self) -> None:
        self.dismiss(None)

    def _confirm(self) -> None:
        choice = self.query_one("#target-choice", RadioSet).pressed_button
        err = self.query_one("#dialog-error", Label)
        providers = ["claude"]
        if self.ask_providers:
            providers = [str(v) for v in
                         self.query_one("#providers", SelectionList).selected]
            if not providers:
                err.update("tick at least one AI assistant")
                return
        if choice is None:
            err.update("pick an option first")
            return
        if choice.id == "opt-user":
            others = [p for p in providers if p != "claude"]
            if others:
                err.update(
                    f"{', '.join(others)} installs are project-scoped — "
                    "pick a project folder for them"
                )
                return
            self.dismiss((Target("user"), providers))
        elif choice.id == "opt-project":
            self.dismiss((Target("project", str(Path.cwd())), providers))
        else:
            raw = self.query_one("#custom-path", Input).value.strip()
            if not raw:
                err.update("enter a folder path (or pick another option)")
                return
            path = Path(raw).expanduser()
            if not path.is_dir():
                err.update(f"no such folder: {path}")
                return
            self.dismiss((Target("project", str(path.resolve())), providers))


class ConfirmDialog(ModalScreen[bool]):
    BINDINGS = [Binding("escape", "no", "Cancel")]

    def __init__(self, question: str, yes_label: str = "Yes") -> None:
        super().__init__()
        self.question = question
        self.yes_label = yes_label

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label(self.question, id="dialog-title")
            with Horizontal(classes="buttons"):
                yield Button(self.yes_label, variant="error", id="yes")
                yield Button("Cancel", id="no")

    @on(Button.Pressed, "#yes")
    def _yes(self) -> None:
        self.dismiss(True)

    @on(Button.Pressed, "#no")
    def action_no(self) -> None:
        self.dismiss(False)


class OutputDialog(ModalScreen[None]):
    """Shows a command's full output — used when something needs reading."""

    BINDINGS = [Binding("escape", "close", "Close")]

    def __init__(self, title: str, body: str) -> None:
        super().__init__()
        self.title_text = title
        self.body = body

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog", classes="wide"):
            yield Label(self.title_text, id="dialog-title")
            with VerticalScroll(id="dialog-body"):
                yield Static(self.body or "(no output)")
            with Horizontal(classes="buttons"):
                yield Button("OK", variant="primary", id="ok")

    @on(Button.Pressed, "#ok")
    def action_close(self) -> None:
        self.dismiss(None)


# --- bundle detail screen --------------------------------------------------------

class BundleScreen(Screen):
    """One bundle: tick the skills/agents you want, then act on them."""

    BINDINGS = [
        Binding("escape", "back", "Back"),
        Binding("a", "select_all", "All / none"),
        Binding("i", "install", "Install"),
        Binding("x", "uninstall", "Uninstall"),
    ]

    def __init__(self, bundle: Bundle, preselect_all: bool = False) -> None:
        super().__init__()
        self.bundle = bundle
        self.preselect_all = preselect_all

    def compose(self) -> ComposeResult:
        b = self.bundle
        head = Text()
        head.append(f" {b.name} ", style="bold reverse")
        head.append(f" v{b.version}", style="dim")
        if b.title:
            head.append(f"  —  {b.title}")
        yield Static(head, id="topbar")
        yield Static("", id="targetbar")
        yield SelectionList(id="items")
        with Horizontal(id="actions"):
            yield Button("Install selected", variant="primary", id="install")
            yield Button("Uninstall selected", id="uninstall")
            yield Button("Select all", id="select-all")
            yield Button("Back", id="back")
        yield Footer()

    def on_mount(self) -> None:
        self.refresh_items(self.preselect_all)
        self.query_one("#items", SelectionList).focus()

    @property
    def app_target(self) -> Target:
        return self.app.target  # type: ignore[attr-defined]

    def refresh_items(self, select_all: bool = False) -> None:
        b = self.bundle
        _, installed = receipt_read(self.app_target.path, b.name)
        sel = self.query_one("#items", SelectionList)
        sel.clear_options()
        for kind, icon, style, names in (
            ("skill", "⚡", "yellow", b.skills),
            ("agent", "◆", "magenta", b.agents),
        ):
            for name in names:
                label = Text()
                label.append(f"{icon} ", style=style)
                label.append(f"{name:<34}")
                label.append(f" {kind} ", style=f"reverse dim {style}")
                if (kind, name) in installed:
                    label.append("  ● installed", style="green")
                sel.add_option((label, f"{kind}:{name}", select_all))
        self.query_one("#targetbar", Static).update(
            Text.assemble(
                ("  target  ", "dim"),
                (self.app_target.pretty, "bold"),
                ("    click or space to tick · installed items show ●", "dim"),
            )
        )

    def _picked(self) -> List[str]:
        sel = self.query_one("#items", SelectionList)
        picked = [str(v).split(":", 1)[1] for v in sel.selected]
        if not picked and sel.highlighted is not None:
            value = sel.get_option_at_index(sel.highlighted).value
            picked = [str(value).split(":", 1)[1]]
        return picked

    def action_select_all(self) -> None:
        sel = self.query_one("#items", SelectionList)
        if len(sel.selected) == sel.option_count:
            sel.deselect_all()
        else:
            sel.select_all()

    def action_back(self) -> None:
        self.app.pop_screen()

    @on(Button.Pressed, "#back")
    def _back_btn(self) -> None:
        self.action_back()

    @on(Button.Pressed, "#select-all")
    def _all_btn(self) -> None:
        self.action_select_all()

    @on(Button.Pressed, "#install")
    def _install_btn(self) -> None:
        self.action_install()

    @on(Button.Pressed, "#uninstall")
    def _uninstall_btn(self) -> None:
        self.action_uninstall()

    def action_install(self) -> None:
        self.run_worker(self.do_install(), exclusive=True)

    def action_uninstall(self) -> None:
        self.run_worker(self.do_uninstall(), exclusive=True)

    async def do_install(self) -> None:
        items = self._picked()
        if not items:
            self.notify("Nothing to install — tick some items first.", severity="warning")
            return
        result = await self.app.push_screen_wait(
            TargetPicker(f"Install {len(items)} item(s) of {self.bundle.name}",
                         self.app_target, ask_providers=True)
        )
        if result is None:
            return
        chosen, providers = result
        self.app.target = chosen  # type: ignore[attr-defined]
        spec = f"{self.bundle.name}:{','.join(items)}"
        args = ["install", spec, *chosen.cli_flags(), "--force"]
        if providers != ["claude"]:
            args += ["--provider", ",".join(providers)]
        code, out = await run_cli(*args)
        if code == 0:
            names = ", ".join(
                label for key, label, _ in PROVIDERS if key in providers
            )
            self.notify(
                f"Installed {len(items)} item(s) for {names} → {chosen.pretty}. "
                "Restart the assistant to load them.",
                title="✓ installed",
            )
        else:
            await self.app.push_screen_wait(OutputDialog("Install failed", out))
        self.refresh_items()

    async def do_uninstall(self) -> None:
        items = self._picked()
        if not items:
            self.notify("Nothing to uninstall — tick some items first.", severity="warning")
            return
        sure = await self.app.push_screen_wait(
            ConfirmDialog(
                f"Remove {len(items)} item(s) of {self.bundle.name} "
                f"from {self.app_target.pretty}?",
                yes_label="Uninstall",
            )
        )
        if not sure:
            return
        spec = f"{self.bundle.name}:{','.join(items)}"
        code, out = await run_cli("uninstall", spec, *self.app_target.cli_flags())
        if code == 0:
            self.notify(f"Removed {len(items)} item(s).", title="✓ uninstalled")
        else:
            await self.app.push_screen_wait(OutputDialog("Uninstall failed", out))
        self.refresh_items()


# --- main screen -----------------------------------------------------------------

class BundleCard(ListItem):
    def __init__(self, bundle: Bundle, target: Path) -> None:
        n = len(receipt_read(target, bundle.name)[1])
        status = "full" if (bundle.total and n >= bundle.total) else (
            "partial" if n else "empty")
        super().__init__(
            Static(self.render_card(bundle, target)),
            classes=f"card st-{status}",
        )
        self.bundle = bundle

    @staticmethod
    def render_card(b: Bundle, target: Path) -> Table:
        grid = Table.grid(expand=True)
        grid.add_column(ratio=1)
        grid.add_column(justify="right")
        line1 = Text()
        line1.append(f" {b.name} ", style="bold reverse")
        line1.append(f" v{b.version}", style="dim")
        line2 = Text()
        if b.title:
            line2.append(b.title, style="italic")
            line2.append("\n")
        line2.append("⚡ ", style="yellow")
        line2.append(f"{len(b.skills)} skills", style="dim")
        line2.append("   ◆ ", style="magenta")
        line2.append(f"{len(b.agents)} agents", style="dim")
        grid.add_row(line1, status_text(b, target))
        grid.add_row(line2, Text())
        return grid


class MainScreen(Screen):
    BINDINGS = [
        Binding("enter", "open", "Open"),
        Binding("i", "install", "Install"),
        Binding("u", "update", "Update"),
        Binding("x", "uninstall", "Uninstall"),
        Binding("t", "target", "Target"),
        Binding("r", "refresh", "Refresh"),
        Binding("q", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        head = Text()
        head.append(" ⬢ claude-packs ", style="bold reverse")
        if VERSION:
            head.append(f" v{VERSION} ", style="dim")
        head.append("  skill & agent bundles — Claude Code · Copilot · Cursor",
                    style="dim italic")
        yield Static(head, id="topbar")
        yield Static("", id="targetbar")
        yield ListView(id="bundles")
        with Horizontal(id="actions"):
            yield Button("Open", variant="primary", id="open")
            yield Button("Install…", id="install")
            yield Button("Update", id="update")
            yield Button("Uninstall", id="uninstall")
            yield Button("Target…", id="target")
            yield Button("Quit", id="quit")
        yield Footer()

    def on_mount(self) -> None:
        self.refresh_bundles()
        self.query_one("#bundles", ListView).focus()

    @property
    def app_target(self) -> Target:
        return self.app.target  # type: ignore[attr-defined]

    def refresh_bundles(self) -> None:
        lv = self.query_one("#bundles", ListView)
        idx = lv.index or 0
        lv.clear()
        for b in load_bundles():
            lv.append(BundleCard(b, self.app_target.path))
        if len(lv) > 0:
            lv.index = min(idx, len(lv) - 1)
        self.query_one("#targetbar", Static).update(
            Text.assemble(
                ("  target  ", "dim"),
                (self.app_target.pretty, "bold"),
                ("    press t or the Target… button to change", "dim"),
            )
        )

    def current(self) -> Optional[Bundle]:
        lv = self.query_one("#bundles", ListView)
        item = lv.highlighted_child
        return item.bundle if isinstance(item, BundleCard) else None

    # open on click / enter
    @on(ListView.Selected, "#bundles")
    def _open_selected(self, event: ListView.Selected) -> None:
        if isinstance(event.item, BundleCard):
            self.app.push_screen(BundleScreen(event.item.bundle))

    def action_open(self) -> None:
        b = self.current()
        if b:
            self.app.push_screen(BundleScreen(b))

    def action_install(self) -> None:
        b = self.current()
        if b:
            self.app.push_screen(BundleScreen(b, preselect_all=True))

    def action_target(self) -> None:
        self.run_worker(self.do_target(), exclusive=True)

    def action_update(self) -> None:
        self.run_worker(self.do_update(), exclusive=True)

    def action_uninstall(self) -> None:
        self.run_worker(self.do_uninstall(), exclusive=True)

    def action_refresh(self) -> None:
        self.refresh_bundles()
        self.notify("Refreshed.", timeout=2)

    @on(Button.Pressed, "#open")
    def _open_btn(self) -> None:
        self.action_open()

    @on(Button.Pressed, "#install")
    def _install_btn(self) -> None:
        self.action_install()

    @on(Button.Pressed, "#update")
    def _update_btn(self) -> None:
        self.action_update()

    @on(Button.Pressed, "#uninstall")
    def _uninstall_btn(self) -> None:
        self.action_uninstall()

    @on(Button.Pressed, "#target")
    def _target_btn(self) -> None:
        self.action_target()

    @on(Button.Pressed, "#quit")
    def _quit_btn(self) -> None:
        self.app.exit()

    async def do_target(self) -> None:
        result = await self.app.push_screen_wait(
            TargetPicker("Show and manage installs for which target?", self.app_target)
        )
        if result is not None:
            self.app.target = result[0]  # type: ignore[attr-defined]
            self.refresh_bundles()

    async def do_update(self) -> None:
        b = self.current()
        if not b:
            return
        code, out = await run_cli("update", b.name, *self.app_target.cli_flags())
        if code == 0:
            await self.app.push_screen_wait(OutputDialog(f"Update — {b.name}", out))
        else:
            await self.app.push_screen_wait(OutputDialog("Update failed", out))
        self.refresh_bundles()

    async def do_uninstall(self) -> None:
        b = self.current()
        if not b:
            return
        _, installed = receipt_read(self.app_target.path, b.name)
        if not installed:
            self.notify(f"{b.name} is not installed at {self.app_target.pretty}.",
                        severity="warning")
            return
        sure = await self.app.push_screen_wait(
            ConfirmDialog(
                f"Uninstall {b.name} ({len(installed)} items) "
                f"from {self.app_target.pretty}?",
                yes_label="Uninstall",
            )
        )
        if not sure:
            return
        code, out = await run_cli("uninstall", b.name, *self.app_target.cli_flags())
        if code == 0:
            self.notify(f"Uninstalled {b.name}.", title="✓ uninstalled")
        else:
            await self.app.push_screen_wait(OutputDialog("Uninstall failed", out))
        self.refresh_bundles()


# --- the app ---------------------------------------------------------------------

class PacksApp(App[None]):
    TITLE = "claude-packs"

    CSS = """
    #topbar {
        dock: top;
        height: 1;
        padding: 0 1;
        background: $panel;
        border-bottom: hkey $primary 40%;
    }
    #targetbar {
        dock: top;
        height: 1;
        padding: 0 1;
        background: $surface;
        color: $text-muted;
    }
    #bundles {
        margin: 1 3;
        background: $surface;
        scrollbar-size-vertical: 1;
    }
    #bundles > ListItem.card {
        padding: 1 2;
        margin-bottom: 1;
        background: $panel;
        border: round $primary 35%;
        border-left: thick $primary 35%;
    }
    #bundles > ListItem.card.st-full    { border-left: thick $success; }
    #bundles > ListItem.card.st-partial { border-left: thick $warning; }
    #bundles > ListItem.card.-highlight, #bundles > ListItem.card:hover {
        border: round $accent;
        border-left: thick $accent;
        background: $primary 12%;
    }
    #items {
        margin: 1 3;
        padding: 0 1;
        border: round $primary 35%;
        background: $surface;
        scrollbar-size-vertical: 1;
    }
    #items:focus {
        border: round $accent;
        background-tint: $accent 4%;
    }
    #actions {
        dock: bottom;
        height: 3;
        align: center middle;
        background: $panel;
        border-top: hkey $primary 40%;
    }
    #actions Button {
        margin: 0 1;
        min-width: 12;
        border: none;
        height: 1;
    }
    #dialog {
        width: 74;
        max-width: 92%;
        height: auto;
        max-height: 85%;
        padding: 1 2;
        background: $panel;
        border: round $accent;
        border-title-align: left;
    }
    #dialog.wide {
        width: 96;
    }
    #dialog-title {
        margin-bottom: 1;
        text-style: bold;
        color: $accent;
    }
    .dialog-section {
        margin-top: 1;
        color: $text-muted;
        text-style: bold;
    }
    #providers {
        height: auto;
        max-height: 6;
        margin: 0 0 0 1;
        background: $panel;
        border: none;
        padding: 0;
    }
    #target-choice {
        background: $panel;
        border: none;
        padding: 0 0 0 1;
    }
    #dialog-body {
        height: auto;
        max-height: 20;
        margin-bottom: 1;
        background: $surface;
        padding: 1;
    }
    #dialog-error {
        color: $text-error;
        height: auto;
    }
    #dialog .buttons {
        height: 3;
        align: right middle;
    }
    #dialog Button {
        margin-left: 2;
        min-width: 10;
    }
    #custom-path {
        margin: 0 0 0 1;
    }
    #custom-path.hidden {
        display: none;
    }
    TargetPicker, ConfirmDialog, OutputDialog {
        align: center middle;
        background: $background 60%;
    }
    Toast {
        background: $panel;
        border-left: thick $success;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        mode = os.environ.get("CLAUDE_PACKS_TARGET_MODE", "user")
        pdir = os.environ.get("CLAUDE_PACKS_PROJECT_DIR", str(Path.cwd()))
        self.target = Target("project" if mode == "project" else "user", pdir)

    def on_mount(self) -> None:
        try:
            self.theme = "tokyo-night"
        except Exception:
            pass  # older Textual without this builtin theme — keep the default
        self.push_screen(MainScreen())


def main() -> None:
    if not (ROOT / "bundles").is_dir():
        print(f"claude-packs-tui: no bundles/ under {ROOT}", file=sys.stderr)
        sys.exit(2)
    PacksApp().run()


if __name__ == "__main__":
    main()
