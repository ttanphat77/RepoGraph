# tui/chat.py — RepoGraph chatbot, full-screen terminal app (Textual + rich + Gemini)
#
# Conversational with memory. The google.genai chat session keeps the full history.
# The model calls the search_repo tool only when a question needs code from the
# Knowledge Graph. Not every message triggers retrieval.
#
# Full-screen (alternate screen) so rendering does not depend on the console
# scrolling its viewport. Layout, top to bottom:
#   header   model, schema, graph status and size, instance, repo, tool
#   chat     scrollable log: "You" bubble → Retrieval panel (if the tool ran) → "Bot" bubble
#   input    message box. Type 'exit' to quit, or press ctrl+q.
#   footer   key bindings
#
# Slash commands (type /help):
#   /model [name]   show or switch the Gemini model, conversation history is kept
#   /schema         active schema and the node labels present in the graph
#   /depth [1-3]    show or set BFS depth for search_repo
#   /bm25 [n]       show or set the BM25 seed limit for search_repo
#   /clear          clear the log and start a new conversation
#   /reload         re-read the instance file and re-check Neo4j
#   /exit           quit
#
# The Retrieval panel shows the 5 stages of pipeline/retriever.py:
#   ① Pre-retrieve  identifiers extracted from the query (regex)
#   ② Seed lookup   table of matched nodes, split by source regex / BM25
#   ③ BFS           subgraph size, edge type breakdown
#   ④ Ranking       table of ranked files, Mix column draws ● seed and ○ other nodes
#   ⑤ Context       table of code sections sent to the LLM, in SEED / CALLER / CALLEE order
#
# Colors carry meaning. Standard color names are used so they fit any terminal theme:
#   green   user, exact match (regex, SEED)
#   cyan    bot
#   yellow  fuzzy match (BM25), CALLER
#   blue    Function, CALLEE
#   magenta Class
#   dim     Module, secondary numbers, trace panel border
#
# Run from the repo root:  .venv\Scripts\python.exe -m tui.chat

import json
import os
import re
import sys
import time
from collections import Counter

# The repo root must be on sys.path because the pipeline does `import config`.
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

# Windows defaults stdout to cp1252. Non-ASCII characters crash on print.
# Force UTF-8 so tracebacks and warnings print on any terminal.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    except Exception:
        pass

import google.genai as genai
from neo4j import GraphDatabase
from rich import box
from rich.console import Group
from rich.markdown import Markdown
from rich.panel import Panel
from rich.spinner import Spinner
from rich.table import Table
from rich.text import Text
from textual import events, work
from textual.app import App, ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Footer, Input, Static

import config
from pipeline.evaluator import run_retrieval_only

# Max rows per table in the trace, so the trace stays short.
_MAX_ROWS = 10

# Each code section header in the context looks like:  [SEED] `name` — file:1-20
_RE_CTX_HEADER = re.compile(r"^\[([A-Za-z_]+)\] `([^`]+)` — (.+)$")

# Colors by node label and by context tag.
_LABEL_STYLE = {
    "Function": "blue", "FUNCTION": "blue", "METHOD": "blue",
    "Class": "magenta", "CLASS": "magenta",
    "Module": "dim", "MODULE": "dim",
}
_TAG_STYLE = {"SEED": "bold green", "CALLER": "yellow", "CALLEE": "blue"}

# Written by scripts/build_graph.py after each build.
_INSTANCE_PATH = os.path.join(_REPO_ROOT, "cache", "current_instance.json")

_SYSTEM = """\
You are an assistant for this code repository. The repository is indexed in a \
Knowledge Graph of modules, classes and functions.

Call the `search_repo` tool when the user asks about the code: files, functions, \
classes, how something works, where something is defined, or how to fix an issue. \
Do not call it for greetings, thanks, or general conversation that does not need \
the code.

When you cite code, use the form `symbol` in `path/to/file:line`. \
Answer in the same language the user writes in.\
"""


# ── Trace building blocks ────────────────────────────────────────────────────
def _stage(num: str, title: str, summary: str) -> Text:
    """Stage header line: circled number, bold title, dim summary."""
    t = Text()
    t.append(f"{num} ", style="bold cyan")
    t.append(f"{title:<13}", style="bold")
    t.append(summary, style="dim")
    return t


def _table(*columns: str) -> Table:
    """Compact borderless table, indented under the stage header."""
    tb = Table(box=None, show_header=True, header_style="dim", pad_edge=False,
               padding=(0, 1), collapse_padding=True)
    tb.add_column(" ", width=2)  # indent column
    for c in columns:
        tb.add_column(c)
    return tb


def _more(n: int) -> list:
    """Dim '… +N' line when a table is truncated."""
    return [Text(f"   … +{n - _MAX_ROWS}", style="dim")] if n > _MAX_ROWS else []


def _retrieval_panel(query: str, r: dict, elapsed: float, depth: int) -> Panel:
    """Build the 5-stage retrieval panel from the dict returned by run_retrieval_only."""
    candidates = r.get("candidates") or []
    seeds = r.get("seed_nodes") or []
    sub = r.get("subgraph") or {"nodes": [], "edges": []}
    files = r.get("candidate_files") or []
    context = r.get("context") or ""
    seed_ids = {n["neo_id"] for n in seeds}

    parts: list = []

    # ① Pre-retrieve
    parts.append(_stage("①", "Pre-retrieve", f"{len(candidates)} identifiers"))
    if candidates:
        idents = Text("   ")
        for i, c in enumerate(candidates[:_MAX_ROWS]):
            if i:
                idents.append(" · ", style="dim")
            idents.append(c, style="green")
        if len(candidates) > _MAX_ROWS:
            idents.append(f" … +{len(candidates) - _MAX_ROWS}", style="dim")
        parts.append(idents)

    # ② Seed lookup. BM25 nodes carry a `score` key, regex nodes do not.
    n_bm25 = sum(1 for n in seeds if "score" in n)
    n_regex = len(seeds) - n_bm25
    parts.append(_stage("②", "Seed lookup",
                        f"{len(seeds)} seeds · regex {n_regex} · bm25 {n_bm25}"))
    if seeds:
        tb = _table("Label", "Name", "Location", "Match")
        for n in seeds[:_MAX_ROWS]:
            label = str(n.get("label") or "")
            loc = f"{n.get('file') or ''}:{n.get('start_line') or ''}"
            if "score" in n:
                match = Text(f"bm25 {n['score']:.2f}", style="yellow")
            else:
                match = Text("exact", style="green")
            tb.add_row("", Text(label, style=_LABEL_STYLE.get(label, "")),
                       Text(str(n.get("name") or ""), style="bold"),
                       Text(loc, style="dim"), match)
        parts.append(tb)
        parts += _more(len(seeds))

    # ③ BFS
    rel = Counter(e["rel_type"] for e in sub["edges"])
    parts.append(_stage("③", f"BFS depth {depth}",
                        f"{len(sub['nodes'])} nodes · {len(sub['edges'])} edges"))
    if rel:
        edges = Text("   ")
        for i, (t, c) in enumerate(rel.most_common()):
            if i:
                edges.append(" · ", style="dim")
            edges.append(t, style="cyan")
            edges.append(f" {c}", style="dim")
        parts.append(edges)

    # ④ Ranking. Count seed and other nodes per file to explain the order.
    per_file: dict[str, list[int]] = {}
    for n in sub["nodes"]:
        f = n.get("file")
        if not f:
            continue
        d = per_file.setdefault(f, [0, 0])
        d[0 if n["neo_id"] in seed_ids else 1] += 1
    parts.append(_stage("④", "Ranking", f"{len(files)} files"))
    if files:
        tb = _table("#", "File", "Seed", "Other", "Mix")
        for i, f in enumerate(files[:_MAX_ROWS], 1):
            s, o = per_file.get(f, (0, 0))
            mix = Text()
            mix.append("●" * min(s, 8), style="green")
            mix.append("○" * min(o, 8), style="dim")
            tb.add_row("", Text(str(i), style="dim"), Text(f, style="bold"),
                       Text(str(s), style="green"), Text(str(o), style="dim"), mix)
        parts.append(tb)
        parts += _more(len(files))

    # ⑤ Context. Read each section header to show the exact order the LLM receives.
    headers = [m for m in (_RE_CTX_HEADER.match(ln) for ln in context.splitlines()) if m]
    parts.append(_stage("⑤", "Context", f"{len(headers)} sections · {len(context)} chars"))
    if headers:
        tb = _table("Tag", "Name", "Location")
        for m in headers[:_MAX_ROWS]:
            tag, name, loc = m.groups()
            tb.add_row("", Text(tag, style=_TAG_STYLE.get(tag, "dim")),
                       Text(name, style="bold"), Text(loc, style="dim"))
        parts.append(tb)
        parts += _more(len(headers))

    title = Text()
    title.append("🔍 Retrieval ", style="bold yellow")
    title.append(f"“{query}”", style="dim")
    title.append(f" · {elapsed:.2f}s", style="dim")
    return Panel(Group(*parts), title=title, title_align="left",
                 border_style="dim", box=box.ROUNDED)


# ── Header ───────────────────────────────────────────────────────────────────
def _graph_stats() -> dict | None:
    """Node, edge and file counts from Neo4j. None if the graph is unreachable.
    Short connection timeout so a down Neo4j does not stall startup. The driver
    tries IPv4 and IPv6 in turn, so the worst case is about twice this value."""
    try:
        driver = GraphDatabase.driver(
            config.NEO4J_URI,
            auth=(config.NEO4J_USER, config.NEO4J_PASSWORD),
            connection_timeout=1.0,
        )
        try:
            driver.verify_connectivity()
            with driver.session() as s:
                nodes = s.run("MATCH (n) RETURN count(n) AS c").single()["c"]
                edges = s.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"]
                files = s.run("MATCH (m) WHERE m:Module OR m:MODULE RETURN count(m) AS c").single()["c"]
            return {"nodes": nodes, "edges": edges, "files": files}
        finally:
            driver.close()
    except Exception:
        return None


def _label_counts() -> dict | None:
    """Node count per label in Neo4j. Tells which schema the graph was built with.
    None if the graph is unreachable."""
    try:
        driver = GraphDatabase.driver(
            config.NEO4J_URI,
            auth=(config.NEO4J_USER, config.NEO4J_PASSWORD),
            connection_timeout=1.0,
        )
        try:
            driver.verify_connectivity()
            with driver.session() as s:
                rows = s.run("MATCH (n) RETURN labels(n)[0] AS label, count(*) AS c ORDER BY c DESC")
                return {r["label"]: r["c"] for r in rows}
        finally:
            driver.close()
    except Exception:
        return None


def _instance() -> dict:
    """Current instance state from cache/current_instance.json. Empty if missing."""
    try:
        with open(_INSTANCE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _header_panel(stats: dict | None, inst: dict, model: str, depth: int,
                  checking: bool = False) -> Panel:
    """Key/value header. checking=True shows the graph status as pending."""
    graph = Text(config.NEO4J_URI)
    if checking:
        graph.append(" ● checking", style="dim")
        size = Text("…", style="dim")
    elif stats:
        graph.append(" ● up", style="green")
        size = Text(f"{stats['nodes']:,} nodes · {stats['edges']:,} edges · {stats['files']:,} files")
    else:
        graph.append(" ● down", style="red")
        size = Text("—", style="dim")

    instance = Text(str(inst.get("instance_id") or "—"))
    gt = inst.get("gt_files") or []
    if gt:
        instance.append(f" · {len(gt)} GT files", style="dim")
    repo, commit = inst.get("repo"), inst.get("base_commit")
    repo_s = f"{repo}@{commit[:7]}" if repo and commit else (repo or "—")

    # Single key/value column. A 2x2 grid fights for width and wraps on narrow terminals.
    g = Table.grid(padding=(0, 2))
    g.add_column(style="dim")
    g.add_column()
    g.add_row("Model", model)
    g.add_row("Schema", config.ACTIVE_SCHEMA)
    g.add_row("Graph", graph)
    g.add_row("Size", size)
    g.add_row("Instance", instance)
    g.add_row("Repo", repo_s)
    g.add_row("Tool", f"search_repo · BFS depth {depth} · BM25 top {config.BM25_SEED_LIMIT}")
    return Panel(g, title="[bold cyan]RepoGraph Chat[/]", title_align="left",
                 subtitle="/help for commands", subtitle_align="right",
                 border_style="cyan", box=box.ROUNDED)


# ── Chat bubbles ─────────────────────────────────────────────────────────────
def _user_bubble(msg: str) -> Panel:
    return Panel(Text(msg), title="You", title_align="left",
                 border_style="green", box=box.ROUNDED)


def _system_bubble(body) -> Panel:
    """Output of a slash command. body is a str, Text, or any rich renderable."""
    return Panel(body, title="System", title_align="left",
                 border_style="dim", box=box.ROUNDED)


# (name, usage, description). Used by /help and by the command list that pops
# up above the input while the text starts with "/".
_COMMANDS = (
    ("/model", "/model [name]", "show or switch the Gemini model, conversation history is kept"),
    ("/schema", "/schema", "active schema and the node labels present in the graph"),
    ("/depth", "/depth [1-3]", "show or set BFS depth for search_repo"),
    ("/bm25", "/bm25 [n]", "show or set the BM25 seed limit for search_repo"),
    ("/clear", "/clear", "clear the log and start a new conversation"),
    ("/reload", "/reload", "re-read the instance file and re-check Neo4j"),
    ("/exit", "/exit", "quit (also: exit, ctrl+q)"),
)


def _command_list(names: list[str] | None = None, selected: int | None = None) -> Text:
    """One line per command. names limits which commands; selected highlights a row."""
    t = Text()
    rows = [c for c in _COMMANDS if names is None or c[0] in names]
    for i, (name, usage, desc) in enumerate(rows):
        line = Text()
        line.append(f"{usage:<15}", style="bold cyan")
        line.append(desc)
        if i == selected:
            line.stylize("reverse")
        t.append_text(line)
        t.append("\n")
    t.rstrip()
    return t


_HELP = _command_list()


class _CommandInput(Input):
    """Input that lets the app take up/down/tab/enter while the command list is shown."""

    def on_key(self, event: events.Key) -> None:
        if self.app.command_key(event.key):  # type: ignore[attr-defined]
            event.prevent_default()
            event.stop()


class _BotView:
    """State of the Bot bubble for one turn. panel() is rebuilt on a timer
    while streaming, so the spinner animates and the elapsed time ticks.
    search_repo updates `status` to signal the tool call."""

    def __init__(self) -> None:
        self.t0 = time.perf_counter()
        self.answer = ""
        self.status = "thinking"
        self.final = False
        self.total = 0.0
        self._spinner = Spinner("dots", style="cyan")

    def panel(self) -> Panel:
        if self.final:
            body = Markdown(self.answer) if self.answer else Text("(no content)", style="dim")
            subtitle = f"{self.total:.1f}s"
        else:
            elapsed = time.perf_counter() - self.t0
            subtitle = f"{elapsed:.1f}s" + (f" · {self.status}" if self.status else "")
            if self.answer:
                body = Text(self.answer + "▌")
            else:
                self._spinner.update(text=Text(self.status, style="dim"))
                body = self._spinner
        return Panel(body, title="Bot", title_align="left",
                     subtitle=subtitle, subtitle_align="right",
                     border_style="cyan", box=box.ROUNDED)


# ── App ──────────────────────────────────────────────────────────────────────
class RepoGraphChat(App):
    CSS = """
    #header { height: auto; }
    #chat { height: 1fr; padding: 0 1; }
    #chat > Static { height: auto; }
    #cmds { height: auto; display: none; }
    """

    def __init__(self) -> None:
        super().__init__()
        self.client = genai.Client(api_key=config.GEMINI_API_KEY)
        self.model = config.GEMINI_MODEL
        self.depth = 2                         # BFS depth, same as the Issue Query tab default
        self.stats: dict | None = None         # last Neo4j check, for header re-renders
        self.chat = self._new_chat()
        self.turn: _BotView | None = None      # bot view of the turn in progress
        self.bot_widget: Static | None = None  # its widget in the chat log
        self._tick = None                      # timer that re-renders the bot bubble
        self._matches: list[str] = []          # commands matching the typed prefix
        self._sel = 0                          # highlighted row in the command list

    def _new_chat(self, history=None):
        return self.client.chats.create(
            model=self.model,
            config=genai.types.GenerateContentConfig(
                system_instruction=_SYSTEM,
                tools=[search_repo],
            ),
            history=history,
        )

    def compose(self) -> ComposeResult:
        yield Static(_header_panel(None, _instance(), self.model, self.depth, checking=True),
                     id="header")
        yield VerticalScroll(id="chat")
        yield Static(id="cmds")  # command list, shown while the input starts with "/"
        yield _CommandInput(placeholder="Type a message. /help for commands, 'exit' to quit.",
                            id="input")
        yield Footer()

    # ── Command list and completion ───────────────────────────────────────────
    def on_input_changed(self, event: Input.Changed) -> None:
        """Track the commands matching the first token while the text starts with '/'."""
        value = event.value.lstrip()
        self._matches = []
        if value.startswith("/"):
            prefix = value.split()[0].lower()
            self._matches = [n for n, _, _ in _COMMANDS if n.startswith(prefix)]
        self._sel = min(self._sel, len(self._matches) - 1) if self._matches else 0
        self._render_cmds()

    def _render_cmds(self) -> None:
        cmds = self.query_one("#cmds", Static)
        if self._matches:
            title = Text("Commands ", style="bold")
            title.append("↑↓ select · Tab/Enter complete", style="dim")
            cmds.update(Panel(_command_list(self._matches, self._sel), title=title,
                              title_align="left", border_style="dim", box=box.ROUNDED))
            cmds.display = True
        else:
            cmds.display = False

    def command_key(self, key: str) -> bool:
        """Handle a key from the input while the command list is shown.
        Returns True if the key was consumed."""
        if not self._matches:
            return False
        if key == "down":
            self._sel = (self._sel + 1) % len(self._matches)
            self._render_cmds()
            return True
        if key == "up":
            self._sel = (self._sel - 1) % len(self._matches)
            self._render_cmds()
            return True
        if key == "tab":
            self._complete()
            return True
        if key == "enter":
            token = self.query_one(Input).value.lstrip().split()[0].lower()
            if token not in [n for n, _, _ in _COMMANDS]:
                self._complete()
                return True
        return False

    def _complete(self) -> None:
        inp = self.query_one(Input)
        inp.value = self._matches[self._sel] + " "
        inp.cursor_position = len(inp.value)

    def on_mount(self) -> None:
        self.query_one(Input).focus()
        self.load_header()

    def _refresh_header(self) -> None:
        self.query_one("#header", Static).update(
            _header_panel(self.stats, _instance(), self.model, self.depth))

    @work(thread=True)
    def load_header(self) -> None:
        """Neo4j check runs in a thread so the UI is not blocked at startup."""
        self.stats = _graph_stats()
        self.call_from_thread(self._refresh_header)

    def _system(self, body) -> None:
        log = self.query_one("#chat", VerticalScroll)
        log.mount(Static(_system_bubble(body)))
        self.call_after_refresh(log.scroll_end, animate=False)

    # ── Slash commands ────────────────────────────────────────────────────────
    def _command(self, line: str) -> None:
        parts = line.split()
        cmd, arg = parts[0].lower(), (parts[1] if len(parts) > 1 else "")

        if cmd == "/help":
            self._system(_HELP)
        elif cmd == "/model":
            if arg:
                self.model = arg
                self.chat = self._new_chat(history=self.chat.get_history())
                self._refresh_header()
                self._system(f"Model set to {arg}. Conversation history kept. "
                             "Takes effect on the next message.")
            else:
                self._system(f"Model: {self.model}")
        elif cmd == "/schema":
            self.show_schema()
        elif cmd == "/depth":
            if arg in ("1", "2", "3"):
                self.depth = int(arg)
                self._refresh_header()
                self._system(f"BFS depth set to {self.depth}.")
            elif arg:
                self._system("Usage: /depth 1|2|3")
            else:
                self._system(f"BFS depth: {self.depth}")
        elif cmd == "/bm25":
            if arg.isdigit() and int(arg) > 0:
                config.BM25_SEED_LIMIT = int(arg)  # read by the retriever on each call
                self._refresh_header()
                self._system(f"BM25 seed limit set to {arg}.")
            elif arg:
                self._system("Usage: /bm25 <positive integer>")
            else:
                self._system(f"BM25 seed limit: {config.BM25_SEED_LIMIT}")
        elif cmd == "/clear":
            self.query_one("#chat", VerticalScroll).remove_children()
            self.chat = self._new_chat()
            self._system("Log cleared. New conversation started.")
        elif cmd == "/reload":
            self.load_header()
            self._system("Reloading instance file and re-checking Neo4j.")
        elif cmd in ("/exit", "/quit"):
            self.exit()
        else:
            self._system(f"Unknown command: {cmd}. Type /help.")

    @work(thread=True)
    def show_schema(self) -> None:
        """Label counts come from Neo4j, so this runs in a thread."""
        counts = _label_counts()
        body = Text()
        body.append("Active schema: ", style="dim")
        body.append(config.ACTIVE_SCHEMA + "\n")
        body.append("Set in config.py. Applies when build_graph.py ingests; "
                    "the retriever matches both label sets.\n", style="dim")
        if counts is None:
            body.append("Graph unreachable, no label counts.", style="red")
        elif not counts:
            body.append("Graph is empty.", style="yellow")
        else:
            body.append("Labels in graph: ", style="dim")
            body.append(" · ".join(f"{k} {v:,}" for k, v in counts.items()))
        self.call_from_thread(self._system, body)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        msg = event.value.strip()
        event.input.value = ""  # also fires Input.Changed, which hides the command list
        if not msg:
            return
        if msg.lower() in ("exit", "quit"):
            self.exit()
            return
        if msg.startswith("/"):
            self._command(msg)
            return

        log = self.query_one("#chat", VerticalScroll)
        log.mount(Static(_user_bubble(msg)))
        self.turn = _BotView()
        self.bot_widget = Static(self.turn.panel())
        log.mount(self.bot_widget)

        # One send at a time on the shared chat session.
        event.input.disabled = True
        self._tick = self.set_interval(1 / 15, self._refresh_bot)
        self.stream(msg)

    def _refresh_bot(self) -> None:
        if self.turn and self.bot_widget:
            self.bot_widget.update(self.turn.panel())
            self.query_one("#chat", VerticalScroll).scroll_end(animate=False)

    @work(thread=True)
    def stream(self, msg: str) -> None:
        turn = self.turn
        try:
            for chunk in self.chat.send_message_stream(msg):
                # Read text parts directly. chunk.text logs a warning on chunks
                # that carry a function call, and would include thought parts.
                cand = chunk.candidates[0] if chunk.candidates else None
                for part in (cand.content.parts if cand and cand.content else None) or []:
                    if part.text and not part.thought:
                        turn.answer += part.text
                        turn.status = ""
        except Exception as e:
            # A bad /model name or an API error shows in the bubble instead of
            # exiting the app and losing the conversation.
            turn.answer += f"\n\n**Error:** {e}"
        turn.final = True
        turn.total = time.perf_counter() - turn.t0
        self.call_from_thread(self._finish)

    def _finish(self) -> None:
        self._tick.stop()
        self.bot_widget.update(self.turn.panel())
        log = self.query_one("#chat", VerticalScroll)
        self.call_after_refresh(log.scroll_end, animate=False)
        inp = self.query_one(Input)
        inp.disabled = False
        inp.focus()
        self.turn = None
        self.bot_widget = None

    def add_before_bot(self, renderable) -> None:
        """Insert a panel above the bot bubble of the turn in progress."""
        log = self.query_one("#chat", VerticalScroll)
        log.mount(Static(renderable), before=self.bot_widget)
        self.call_after_refresh(log.scroll_end, animate=False)


# The running app. search_repo is called by the SDK from the stream worker
# thread and needs it to post the retrieval panel into the chat log.
_app: RepoGraphChat | None = None


# ── Tool exposed to the model ────────────────────────────────────────────────
def search_repo(query: str) -> str:
    """Search the repository Knowledge Graph for code related to the query.

    Args:
        query: A function name, class name, keyword, or a description of the problem.
    """
    app = _app
    depth = app.depth if app else 2
    if app and app.turn:
        app.turn.status = f"calling search_repo · {query}"
    t0 = time.perf_counter()
    result = run_retrieval_only(query, depth=depth)
    panel = _retrieval_panel(query, result, time.perf_counter() - t0, depth)
    if app:
        app.call_from_thread(app.add_before_bot, panel)
        if app.turn:
            app.turn.status = "generating"
    return result.get("context", "") or ""


def main() -> None:
    global _app
    _app = RepoGraphChat()
    _app.run()


if __name__ == "__main__":
    main()
