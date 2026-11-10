# ChangeFreeze — quiet window for shipping

Same story as the project home page.

1. Set a quiet window.
2. Hermes asks before it ships during that window.
3. Everyday work still runs.

`/freeze on` starts a window with no end time. The ChangeFreeze tools the helper can call cannot end it, shorten it, or allow a ship. File edits and shell commands can still change `state.json` or `allowlist.json` and undo the window. The ship check reads command text. It is not a sandbox.

[Short demo](https://github.com/arults/hermes-changefreeze/releases/download/v0.1.0-demo/changefreeze-demo.mp4) · [Project](https://github.com/arults/hermes-changefreeze) · [Hackathon listing](https://github.com/NousResearch/hermes-agent/pull/149474)
