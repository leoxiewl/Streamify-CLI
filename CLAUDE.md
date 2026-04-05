# Streamify Project Notes

## Command Generation Rules

When generating shell commands for the user:

1. **Use `python3` not `python`** — this Mac does not have `python` in PATH, only `python3`.
2. **Keep commands on a single line** — never let命令换行拆分，尤其是子命令和参数之间（如 `download` 和 URL 必须在同一行），否则终端会把第二行当作独立命令执行。
