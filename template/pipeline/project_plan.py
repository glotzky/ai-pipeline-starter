"""Create one queued [idea] issue per slice from the project planner's JSON answer.

Usage: python pipeline/project_plan.py <planner-output-file> <project-issue-number>
Needs the GitHub CLI (gh) with a token in GH_TOKEN. Nothing is built; issues are only created.
"""
import json
import re
import subprocess
import sys


def parse_slices(text):
    """Pull the JSON array out of the model's answer (tolerates stray text or code fences)."""
    start, end = text.find("["), text.rfind("]")
    if start == -1 or end <= start:
        raise ValueError("No JSON array found in the planner output.")
    data = json.loads(text[start:end + 1])
    slices = []
    for item in data:
        title = str(item.get("title", "")).strip()
        brief = str(item.get("brief", "")).strip()
        if title and brief:
            slices.append({"title": re.sub(r"\s+", " ", title)[:60], "brief": brief})
    if not slices:
        raise ValueError("The planner returned no usable slices.")
    return slices[:15]


def gh(*args, check=True):
    r = subprocess.run(["gh", *args], capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args)} failed:\n{r.stdout}\n{r.stderr}")
    return r.stdout.strip()


def main():
    out_file, project = sys.argv[1], sys.argv[2]
    try:
        slices = parse_slices(open(out_file).read())
    except Exception as e:
        gh("issue", "comment", project, "--body",
           f"I could not turn that plan into slices: {e}\nEdit the issue (more detail often helps) and open a new `[project]` issue.")
        raise SystemExit(1)

    gh("label", "create", "queued", "--color", "fbca04", "--description", "Waiting in the build queue", check=False)
    gh("label", "create", "running", "--color", "1d76db", "--description", "Pipeline is building this", check=False)

    total = len(slices)
    lines = []
    for i, sl in enumerate(slices, 1):
        body = f"{sl['brief']}\n\n---\nSlice {i} of {total} from project #{project}."
        url = gh("issue", "create", "--title", f"[idea] {i}/{total} {sl['title']}",
                 "--body", body, "--label", "queued")
        lines.append(f"{i}. {sl['title']}: {url}")
    gh("issue", "comment", project, "--body",
       "I created these queued ideas, in build order. Edit or close any you do not want.\n\n"
       + "\n".join(lines)
       + "\n\nNothing is built yet. Reply `/queue start` on any issue to build the first one. "
         "After you merge each pull request, the next one is offered (or starts automatically if "
         "the repository variable `PIPELINE_AUTO_QUEUE` is `true`).")


if __name__ == "__main__":
    main()
