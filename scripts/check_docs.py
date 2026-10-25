"""Vérifier les destinations et ancres des liens Markdown locaux."""

import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parent.parent


def anchors(path: Path) -> set[str]:
    result = set()
    counts = {}
    for heading in re.findall(r"^#{1,6}\s+(.+)$", path.read_text(), re.MULTILINE):
        slug = re.sub(r"[^\w -]", "", heading.lower()).replace(" ", "-")
        count = counts.get(slug, 0)
        result.add(f"{slug}-{count}" if count else slug)
        counts[slug] = count + 1
    return result


def main() -> None:
    errors = []
    documents = [*sorted(ROOT.glob("*.md")), *sorted((ROOT / "docs").rglob("*.md")),
                 *sorted((ROOT / ".github").rglob("*.md"))]
    for document in documents:
        for raw in re.findall(r"\]\(([^\s)]+)\)", document.read_text()):
            target = urlsplit(raw.strip("<>"))
            if target.scheme or target.netloc:
                continue
            destination = (document.parent / unquote(target.path)).resolve() if target.path else document
            if not destination.is_relative_to(ROOT) or not destination.is_file():
                errors.append(f"{document.relative_to(ROOT)} : destination absente ({raw})")
            elif target.fragment and destination.suffix == ".md" and unquote(target.fragment) not in anchors(destination):
                errors.append(f"{document.relative_to(ROOT)} : ancre absente ({raw})")
    if errors:
        sys.exit("\n".join(errors))
    print(f"Documentation : {len(documents)} fichiers, liens et ancres locaux valides.")


if __name__ == "__main__":
    main()
