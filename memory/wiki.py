import logging
import os
from pathlib import Path
from typing import Optional

from llm.client import LLMClient, FAST_MODEL, ANALYSIS_MODEL

logger = logging.getLogger(__name__)

WIKI_BASE = Path(__file__).parent.parent / "knowledge" / "wiki"


def _ensure_wiki_dirs():
    WIKI_BASE.mkdir(parents=True, exist_ok=True)
    (WIKI_BASE / "symbols").mkdir(parents=True, exist_ok=True)
    raw_dir = WIKI_BASE.parent / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)


def _read_wiki_file(path: Path) -> str:
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def _write_wiki_file(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.strip() + "\n", encoding="utf-8")


def _log_raw(text: str):
    raw_dir = WIKI_BASE.parent / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    ts = __import__("datetime").datetime.now().isoformat()
    (raw_dir / "inputs.log").open("a", encoding="utf-8").write(f"[{ts}] {text}\n")


async def ingest_note(text: str, symbol: Optional[str] = None) -> str:
    _ensure_wiki_dirs()
    _log_raw(text)

    strategy = _read_wiki_file(WIKI_BASE / "strategy.md")
    patterns = _read_wiki_file(WIKI_BASE / "patterns.md")
    lessons = _read_wiki_file(WIKI_BASE / "lessons.md")
    regime = _read_wiki_file(WIKI_BASE / "regime.md")
    symbol_wiki = ""
    if symbol:
        symbol_wiki = _read_wiki_file(WIKI_BASE / "symbols" / f"{symbol.upper()}.md")

    current_wiki = f"""## strategy.md
{strategy or "(empty)"}

## patterns.md
{patterns or "(empty)"}

## lessons.md
{lessons or "(empty)"}

## regime.md
{regime or "(empty)"}"""

    if symbol_wiki:
        current_wiki += f"\n\n## symbols/{symbol.upper()}.md\n{symbol_wiki}"

    prompt = f"""You maintain a trading wiki. The user has provided new input below.

CURRENT WIKI:
{current_wiki}

NEW INPUT: {text}
{f"Symbol: {symbol}" if symbol else ""}

Update the relevant wiki sections based on this new input. Return ONLY a JSON object with keys matching the filenames to update (strategy.md, patterns.md, lessons.md, regime.md, symbols_SYMBOL). Include ONLY the sections that change. Each value is the FULL new content for that file.

Example:
{{
  "strategy.md": "# Strategy\\n\\nUpdated content...",
  "symbols_AAPL.md": "# AAPL\\n\\nUpdated content..."
}}"""

    llm = LLMClient(model=FAST_MODEL)
    messages = [{"role": "user", "content": prompt}]
    result = await llm.complete_json(messages, temperature=0.2, use_cache=False)

    for key, content in result.items():
        if key == "symbols_SYMBOL" and symbol:
            _write_wiki_file(WIKI_BASE / "symbols" / f"{symbol.upper()}.md", content)
        elif key in ("strategy.md", "patterns.md", "lessons.md", "regime.md"):
            _write_wiki_file(WIKI_BASE / key, content)
        elif symbol and key == f"symbols_{symbol.upper()}.md":
            _write_wiki_file(WIKI_BASE / "symbols" / f"{symbol.upper()}.md", content)

    updated = [k for k in result]
    return f"Wiki updated: {', '.join(updated)}"


async def query_wiki(symbol: Optional[str] = None) -> str:
    _ensure_wiki_dirs()
    parts = []

    strategy = _read_wiki_file(WIKI_BASE / "strategy.md")
    if strategy:
        parts.append(f"# Strategy\n{strategy}")

    patterns = _read_wiki_file(WIKI_BASE / "patterns.md")
    if patterns:
        parts.append(f"# Patterns\n{patterns}")

    if symbol:
        sym_path = WIKI_BASE / "symbols" / f"{symbol.upper()}.md"
        sym_content = _read_wiki_file(sym_path)
        if sym_content:
            parts.append(f"# {symbol.upper()}\n{sym_content}")

    return "\n\n---\n\n".join(parts) if parts else ""


async def lint_wiki() -> str:
    _ensure_wiki_dirs()
    all_content = []
    for f in sorted(WIKI_BASE.glob("*.md")):
        content = _read_wiki_file(f)
        all_content.append(f"--- {f.name} ---\n{content}")
    for f in sorted((WIKI_BASE / "symbols").glob("*.md")):
        content = _read_wiki_file(f)
        all_content.append(f"--- symbols/{f.name} ---\n{content}")

    wiki_text = "\n\n".join(all_content)
    prompt = f"""You are a wiki linter. Review this trading wiki for issues:

{wiki_text}

Check for:
1. **Contradictions** — rules that conflict (e.g., "always cut at 5%" vs "hold through volatility")
2. **Stale claims** — outdated assertions without timestamps
3. **Orphan pages** — symbol pages for symbols not in watchlist
4. **Data gaps** — missing critical sections

Return JSON:
{{
  "issues": [
    {{"severity": "high|medium|low", "file": "strategy.md", "description": "...", "suggestion": "..."}}
  ],
  "healthy": true/false,
  "summary": "overall health assessment"
}}"""

    llm = LLMClient(model=ANALYSIS_MODEL)
    messages = [{"role": "user", "content": prompt}]
    result = await llm.complete_json(messages, temperature=0.1, use_cache=False)

    issues = result.get("issues", [])
    healthy = result.get("healthy", True)
    summary = result.get("summary", "")

    if healthy and not issues:
        return "Wiki health check: \u2705 All clean \u2014 no contradictions, stale claims, or issues found."

    lines = [f"Wiki health check: {'⚠️ Issues found' if not healthy else 'Minor concerns'}", ""]
    for issue in issues:
        icon = {"high": "\U0001f534", "medium": "\U0001f7e1", "low": "\U0001f7e2"}.get(issue.get("severity", "low"), "\u26aa")
        lines.append(f"{icon} [{issue['severity'].upper()}] {issue['file']}: {issue['description']}")
        lines.append(f"   Suggestion: {issue['suggestion']}")
        lines.append("")
    if summary:
        lines.append(f"Summary: {summary}")

    return "\n".join(lines)
