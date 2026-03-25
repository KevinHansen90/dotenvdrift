from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from dotenvdrift.cli import main, render_json
from dotenvdrift.core import audit


def write(root: Path, relative_path: str, text: str) -> None:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class AuditTests(unittest.TestCase):
    def run_cli(self, argv: list[str]) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = main(argv)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_reports_missing_undocumented_and_unused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, ".env.example", "APP_ENV=dev\nDEBUG_SQL=false\nSHARED_KEY=1\n")
            write(
                root,
                "app.py",
                "import os\nOPENAI_API_KEY = os.getenv('OPENAI_API_KEY')\nSHARED_KEY = os.environ['SHARED_KEY']\n",
            )
            write(
                root,
                ".github/workflows/release.yml",
                "name: release\n"
                "on: push\n"
                "jobs:\n"
                "  ship:\n"
                "    runs-on: ubuntu-latest\n"
                "    env:\n"
                "      RELEASE_REGION: us-east-1\n"
                "    steps:\n"
                "      - run: echo ${{ secrets.PYPI_TOKEN }}\n",
            )
            write(
                root,
                "docker-compose.yml",
                "services:\n"
                "  api:\n"
                "    environment:\n"
                "      DATABASE_URL: ${DATABASE_URL}\n",
            )

            result = audit(root)

            self.assertEqual([issue.name for issue in result.missing], ["OPENAI_API_KEY"])
            self.assertEqual(
                [issue.name for issue in result.undocumented],
                ["DATABASE_URL", "PYPI_TOKEN", "RELEASE_REGION"],
            )
            self.assertEqual([issue.name for issue in result.unused], ["APP_ENV", "DEBUG_SQL"])

    def test_json_output_shape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, ".env.example", "APP_ENV=dev\n")
            payload = json.loads(render_json(audit(root), None))
            self.assertEqual(payload["counts"]["total"], 1)
            self.assertIn("unused", payload["issues"])

    def test_json_only_filters_counts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, ".env.example", "APP_ENV=dev\n")
            write(root, "app.py", "import os\nos.getenv('OPENAI_API_KEY')\n")

            payload = json.loads(render_json(audit(root), "missing"))

            self.assertEqual(
                payload["counts"],
                {"missing": 1, "undocumented": 0, "unused": 0, "total": 1},
            )
            self.assertEqual(sorted(payload["issues"]), ["missing"])

    def test_strict_exit_code(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, ".env.example", "APP_ENV=dev\n")

            code, _, _ = self.run_cli([str(root), "--strict"])

            self.assertEqual(code, 1)

    def test_missing_path_returns_error(self) -> None:
        code, _, stderr = self.run_cli(["/tmp/dotenvdrift-missing-path"])

        self.assertEqual(code, 2)
        self.assertIn("repository path not found", stderr)

    def test_ignores_node_modules(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "node_modules/pkg/.env.example", "IGNORED=1\n")
            write(root, "app/app.py", "import os\nos.getenv('LIVE_KEY')\n")

            result = audit(root)

            self.assertEqual([issue.name for issue in result.missing], ["LIVE_KEY"])
            self.assertEqual(result.unused, [])

    def test_compose_environment_list_entries_are_scanned(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(
                root,
                "docker-compose.yml",
                "services:\n"
                "  api:\n"
                "    environment:\n"
                "      - DATABASE_URL=${DATABASE_URL}\n",
            )

            result = audit(root)

            self.assertEqual([issue.name for issue in result.undocumented], ["DATABASE_URL"])


if __name__ == "__main__":
    unittest.main()
