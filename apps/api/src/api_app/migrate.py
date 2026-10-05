"""Apply numbered SQL files once. The API does this before it listens."""

from pathlib import Path

from api_app.config import get_settings
from api_app import db


def apply() -> None:
    directory = Path(get_settings().migrations_dir)
    scripts = sorted(path for path in directory.glob("*.sql") if path.is_file())
    if not scripts:
        raise RuntimeError(f"No SQL files in {directory}")
    first = scripts[0].read_text(encoding="utf-8")
    db.execute_script(first)
    done = db.applied_versions()
    for path in scripts:
        if path.name in done:
            continue
        if path != scripts[0]:
            db.execute_script(path.read_text(encoding="utf-8"))
        db.mark_applied(path.name)
