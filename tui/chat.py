# tui/chat.py — RepoGraph chatbot, full-screen terminal app (Textual + rich + Gemini)
#
# Hai chế độ (/mode):
#   prompt (mặc định)  Mỗi tin nhắn là một lần prompting riêng (giai đoạn 1 của app): truy hồi
#                      K(p) đa nguồn, gọi Gemini một lần, ghi bản ghi lần chạy. Không có
#                      history hội thoại, không có tool.
#   chat               Hội thoại có memory (chat session của google.genai giữ history). Model
#                      gọi tool search_repo khi cần, tool trả K(p) của query do model viết.
#                      Giữ làm nền cho agent ở giai đoạn 2; chưa được đo.
#
# Full-screen (alternate screen) so rendering does not depend on the console
# scrolling its viewport. Layout, top to bottom:
#   header   model, mode, repo and index, graph status
#   chat     scrollable log: "You" bubble → K(p) panel → "Bot" bubble
#   input    message box. Type 'exit' to quit, or press ctrl+q.
#   footer   key bindings
#
# Slash commands (type /help):
#   /mode [prompt|chat]  show or switch the mode
#   /model [name]        show or switch the Gemini model, conversation history is kept
#   /schema              active schema and the node labels present in the graph
#   /clear               clear the log and start a new conversation
#   /reload              re-read the index state and re-check Neo4j
#   /exit                quit
#
# The K(p) panel shows one table per section of the retrieved context: [E] entities named in
# the prompt, [C] code, [D] documentation, [H] past commits, [I] past bug reports. In prompt
# mode it also marks the cited items (✓) and ends with the metrics line and the record path.
#
# Run from the repo root:  .venv\Scripts\python.exe -m tui.chat

import json
import os
import sys
import time
from pathlib import Path

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
from pipeline.context import format_sections, retrieve_kp
from pipeline.evaluator import get_engine, run_prompt
from pipeline.generator import count_section_tokens, stream_answer
from pipeline.run_record import latest_index_dir, retrieval_block
from tui.kp_render import kp_tables, metrics_line

_SYSTEM = """\
You are an assistant for this code repository. The repository is indexed in a \
multi-source graph of code, documentation, past commits and past bug reports.

Call the `search_repo` tool when the user asks about the code: files, functions, \
classes, how something works, where something is defined, why something changed, \
or how to fix an issue. Write the query as a self-contained English sentence. \
Do not call it for greetings, thanks, or general conversation that does not need \
the code.

The tool returns context items with ids such as [C2] or [D1]. Cite code as \
`symbol` in `path/to/file:line` and cite items by their id. \
Answer in the same language the user writes in.\
"""


# ── K(p) panel ───────────────────────────────────────────────────────────────
def _kp_panel(title: str, retrieval: dict, footer: str = "", warnings: list[str] | None = None) -> Panel:
    """Bảng của từng phần K(p), cảnh báo, và dòng số liệu."""
    parts: list = []
    for t in kp_tables(retrieval):
        parts += [t, Text("")]
    for w in warnings or []:
        parts.append(Text(f"warning: {w}", style="yellow"))
    if footer:
        parts.append(Text(footer, style="dim"))
    return Panel(Group(*parts), title=Text(title, style="bold yellow"), title_align="left",
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


def _index_state(index_dir: Path | None) -> dict:
    """index_state.json of the index the app answers from. Empty if missing."""
    try:
        return json.loads((index_dir / "index_state.json").read_text(encoding="utf-8"))
    except Exception:
        return {}


def _header_panel(stats: dict | None, state: dict, index_dir: Path | None, model: str, mode: str,
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

    head = state.get("head_sha") or ""
    repo = Text(f"{state.get('remote') or state.get('repo_path') or '—'}" + (f"@{head[:8]}" if head else ""))
    n = state.get("nodes") or {}
    index = Text(str(index_dir) if index_dir else "— (run scripts/build_graph.py first)")
    if n:
        index.append(f" · code {n.get('Function', 0) + n.get('Class', 0):,} · doc chunks {n.get('DocChunk', 0):,}"
                     f" · commits {n.get('Commit', 0):,} · issues {n.get('Issue', 0):,}", style="dim")

    mode_t = Text(mode, style="bold")
    mode_t.append("  one prompt = one retrieval + one LLM call" if mode == "prompt"
                  else "  conversation with memory, model calls search_repo", style="dim")

    # Single key/value column. A 2x2 grid fights for width and wraps on narrow terminals.
    g = Table.grid(padding=(0, 2))
    g.add_column(style="dim")
    g.add_column()
    g.add_row("Model", model)
    g.add_row("Mode", mode_t)
    g.add_row("Repo", repo)
    g.add_row("Index", index)
    g.add_row("Graph", graph)
    g.add_row("Size", size)
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
    ("/mode", "/mode [name]", "show or switch the mode: prompt (one-shot, default) or chat"),
    ("/model", "/model [name]", "show or switch the Gemini model, conversation history is kept"),
    ("/schema", "/schema", "active schema and the node labels present in the graph"),
    ("/clear", "/clear", "clear the log and start a new conversation"),
    ("/reload", "/reload", "re-read the index state and re-check Neo4j"),
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
    The retrieval step and search_repo update `status`."""

    def __init__(self, status: str = "thinking") -> None:
        self.t0 = time.perf_counter()
        self.answer = ""
        self.status = status
        self.final = False
        self.total = 0.0
        self.footer = ""
        self._spinner = Spinner("dots", style="cyan")

    def panel(self) -> Panel:
        if self.final:
            body = Markdown(self.answer) if self.answer else Text("(no content)", style="dim")
            subtitle = self.footer or f"{self.total:.1f}s"
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
        self.mode = "prompt"
        self.index_dir = latest_index_dir()
        self.state = _index_state(self.index_dir)
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
        yield Static(_header_panel(None, self.state, self.index_dir, self.model, self.mode, checking=True),
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
            _header_panel(self.stats, self.state, self.index_dir, self.model, self.mode))

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
        elif cmd == "/mode":
            if arg in ("prompt", "chat"):
                self.mode = arg
                self._refresh_header()
                self._system(f"Mode set to {arg}.")
            elif arg:
                self._system("Usage: /mode prompt|chat")
            else:
                self._system(f"Mode: {self.mode}")
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
        elif cmd == "/clear":
            self.query_one("#chat", VerticalScroll).remove_children()
            self.chat = self._new_chat()
            self._system("Log cleared. New conversation started.")
        elif cmd == "/reload":
            self.index_dir = latest_index_dir()
            self.state = _index_state(self.index_dir)
            self.load_header()
            self._system("Reloading the index state and re-checking Neo4j.")
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
        body.append("Set in config.py. Applies when build_graph.py ingests.\n", style="dim")
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
        if self.mode == "prompt" and self.index_dir is None:
            self._system("No built index. Run scripts/build_graph.py first, then /reload.")
            return

        log = self.query_one("#chat", VerticalScroll)
        log.mount(Static(_user_bubble(msg)))
        self.turn = _BotView("retrieving context" if self.mode == "prompt" else "thinking")
        self.bot_widget = Static(self.turn.panel())
        log.mount(self.bot_widget)

        # One send at a time.
        event.input.disabled = True
        self._tick = self.set_interval(1 / 15, self._refresh_bot)
        if self.mode == "prompt":
            self.ask(msg)
        else:
            self.stream(msg)

    def _refresh_bot(self) -> None:
        if self.turn and self.bot_widget:
            self.bot_widget.update(self.turn.panel())
            self.query_one("#chat", VerticalScroll).scroll_end(animate=False)

    @work(thread=True)
    def ask(self, msg: str) -> None:
        """Prompt mode: one run_prompt call. K(p) panel and metrics appear when the run ends."""
        turn = self.turn

        def _on_text(s: str) -> None:
            turn.status = ""
            turn.answer += s

        model = self.model
        try:
            rec, run_dir = run_prompt(
                msg, index_dir=self.index_dir, on_text=_on_text,
                llm=lambda system, user, cb: stream_answer(system, user, cb, model=model),
                counter=lambda parts: count_section_tokens(parts, model=model))
            if not turn.answer:
                turn.answer = (run_dir / "answer.md").read_text(encoding="utf-8")
            if rec.get("retrieval"):
                self.call_from_thread(self.add_before_bot, _kp_panel(
                    f"K(p) · {(rec['timing'].get('total_ms') or 0) / 1000:.1f}s", rec["retrieval"],
                    metrics_line(rec, run_dir), rec["warnings"]))
            elif rec["warnings"]:
                turn.answer += "\n\n" + "\n".join(f"**Warning:** {w}" for w in rec["warnings"])
            llm = rec.get("llm") or {}
            turn.footer = (f"{(rec['timing'].get('total_ms') or 0) / 1000:.1f}s · in "
                           f"{llm.get('prompt_token_count') or 0:,} · out {llm.get('candidates_token_count') or 0:,}")
        except Exception as e:
            turn.answer += f"\n\n**Error:** {e}"
        turn.final = True
        turn.total = time.perf_counter() - turn.t0
        self.call_from_thread(self._finish)

    @work(thread=True)
    def stream(self, msg: str) -> None:
        """Chat mode: the chat session streams, the model may call search_repo."""
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
# thread and needs it to post the K(p) panel into the chat log.
_app: RepoGraphChat | None = None


# ── Tool exposed to the model (chat mode) ────────────────────────────────────
def search_repo(query: str) -> str:
    """Search the repository for code, documentation, past commits and past bug reports related to the query.

    Args:
        query: A self-contained description of what to look for: a function or class name, a behavior, or a problem.
    """
    app = _app
    if app is None or app.index_dir is None:
        return "No built index is available."
    if app.turn:
        app.turn.status = f"calling search_repo · {query}"
    t0 = time.perf_counter()
    kp = retrieve_kp(get_engine(app.index_dir), query, time.time(), {})
    sections = format_sections(kp)
    panel = _kp_panel(f"search_repo “{query}” · {time.perf_counter() - t0:.2f}s", retrieval_block(kp, set()))
    app.call_from_thread(app.add_before_bot, panel)
    if app.turn:
        app.turn.status = "generating"
    titles = {"entities": "Entities named in the query [E]", "code": "Code [C]", "files": "Files",
              "doc": "Documentation passages [D]", "hist": "Past commits [H]", "issue": "Past bug reports [I]"}
    return "\n\n".join(f"### {titles[k]}\n\n{v}" for k, v in sections.items())


def main() -> None:
    global _app
    _app = RepoGraphChat()
    _app.run()


if __name__ == "__main__":
    main()
