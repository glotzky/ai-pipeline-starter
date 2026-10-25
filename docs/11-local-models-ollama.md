# 11. Local models (Ollama): optional, and probably not worth it

Nothing in the pipeline needs your computer. Everything runs on GitHub Actions, the Anthropic API and Devin. Local models are an optional cost experiment, and **untested here**.

## Why it is not a drop-in swap

- **GitHub Actions cannot reach a model on your home machine.** You would need a self-hosted runner or a private tunnel, and the machine would have to stay on. That removes the "no always-on computer" benefit.
- **Small local models are weaker at planning and review**, which are the stages that catch mistakes before Devin builds. Models that fit on a cheap machine (about 7B-14B parameters) are noticeably worse at long, tool-using tasks.
- **The pipeline calls the Claude CLI.** Pointing it at Ollama needs a compatibility layer that was not verified. Devin, the builder, stays in the cloud either way.

## If you want to try

1. Install Ollama on a machine you already own and try a model on the cheap stages first (the interviewer is the lowest risk).
2. Compare its output to Claude's on the same idea before changing anything.
3. Only then consider a self-hosted runner. See [multiple projects and hosting](06-multiple-projects-and-hosting.md).

## Hardware, if you do buy something

RAM matters more than CPU. About 16 GB runs 7B-8B models comfortably; useful larger models want 32 GB or more. Check current prices yourself; they change.
