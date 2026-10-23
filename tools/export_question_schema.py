"""Export deterministic schemas; --check fails when committed contracts drift."""

import argparse
import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root / "backend"))
from study_workbench.question_protocol import QuestionBundle, QuestionDocument  # noqa: E402

parser = argparse.ArgumentParser()
parser.add_argument("--check", action="store_true")
args = parser.parse_args()
for filename, model in (
    ("question-v1.schema.json", QuestionDocument),
    ("question-bundle-v1.schema.json", QuestionBundle),
):
    schema = model.model_json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    content = json.dumps(schema, ensure_ascii=False, indent=2) + "\n"
    path = root / "contracts" / filename
    if args.check:
        if not path.exists() or path.read_text(encoding="utf-8") != content:
            raise SystemExit(f"Contract drift: regenerate {filename}")
    else:
        path.write_text(content, encoding="utf-8")
print("Question schemas are current")
