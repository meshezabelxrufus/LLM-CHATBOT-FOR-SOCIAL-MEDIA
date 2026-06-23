"""
Loads and renders Jinja2 prompt templates from the prompts/templates/ directory.

The authoritative system prompt lives in system_prompt.md — it is loaded once
and injected into the Jinja2 template so channel/language context can be appended.
Keeping prompts in files lets non-engineers iterate on wording without touching code.
"""
from functools import cached_property
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

PROMPTS_DIR = Path(__file__).parent
TEMPLATES_DIR = PROMPTS_DIR / "templates"
SYSTEM_PROMPT_FILE = PROMPTS_DIR / "system_prompt.md"


class PromptManager:
    def __init__(
        self,
        templates_dir: Path = TEMPLATES_DIR,
        system_prompt_file: Path = SYSTEM_PROMPT_FILE,
    ) -> None:
        self._env = Environment(
            loader=FileSystemLoader(str(templates_dir)),
            undefined=StrictUndefined,
            autoescape=False,
        )
        self._system_prompt_file = system_prompt_file

    @cached_property
    def _system_prompt_content(self) -> str:
        return self._system_prompt_file.read_text(encoding="utf-8")

    def render(self, template_name: str, **context) -> str:
        template = self._env.get_template(template_name)
        return template.render(**context)

    def system_prompt(self, channel: str, language: str = "auto") -> str:
        return self.render(
            "system_prompt.j2",
            system_prompt_content=self._system_prompt_content,
            channel=channel,
            language=language,
        )

    def rag_context_prompt(self, chunks: list[dict]) -> str:
        return self.render("rag_context.j2", chunks=chunks)
