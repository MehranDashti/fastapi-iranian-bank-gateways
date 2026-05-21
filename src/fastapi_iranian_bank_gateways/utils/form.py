from pathlib import Path
from typing import Any

_TEMPLATES_DIR = Path(__file__).parent.parent / "templates"


def render_auto_submit_form(
    action: str,
    fields: dict[str, Any],
    method: str = "POST",
    template_name: str = "generic_form.html",
) -> str:
    """Render an HTML page with a hidden auto-submit form."""
    try:
        from jinja2 import Environment, FileSystemLoader, select_autoescape

        env = Environment(
            loader=FileSystemLoader(str(_TEMPLATES_DIR)),
            autoescape=select_autoescape(["html"]),
        )
        tmpl = env.get_template(template_name)
        return tmpl.render(action=action, method=method, fields=fields)
    except ImportError:
        # Fallback: inline template (no jinja2 — should not happen since it's a dependency)
        inputs = "".join(
            f'<input type="hidden" name="{k}" value="{v}">' for k, v in fields.items()
        )
        return (
            f'<!DOCTYPE html><html><body>'
            f'<form id="f" method="{method}" action="{action}" style="display:none">'
            f'{inputs}</form>'
            f'<script>document.getElementById("f").submit();</script>'
            f'</body></html>'
        )
