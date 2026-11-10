---
name: changefreeze
description: Quiet window so Hermes asks before it ships code.
---

# ChangeFreeze

An AI helper can ship code at a bad time and break something that is live.

You set a quiet window. During that window, Hermes asks you before it ships. Everyday work still runs. When the window ends, shipping continues again.

The person starts a window with no end time with `/freeze on`, sets an end with `/freeze until`, ends it with `/freeze off`, and lets one ship through with `/freeze allow-once`.

The ChangeFreeze tools you can call cannot end the window, shorten it, or allow a ship. Do not claim that you cannot undo the window at all. If you can edit files or run a shell command, you can change `state.json` or `allowlist.json` and undo it. This plugin does not block those edits. Do not do that to get around the window.

Hermes reads the text of terminal commands and code cells. A cell that contains a ship command written out, including `subprocess.run(["git", "push"])`, is asked about first. If the words are built from pieces, encoded, or hidden, this check does not see them. It is a text check, not a sandbox. `git -C <dir> push` and `git -c <opt> push` are also missed.

Install: `hermes plugins install arults/hermes-changefreeze --enable`

Short demo: https://github.com/arults/hermes-changefreeze/releases/download/v0.1.0-demo/changefreeze-demo.mp4

Project: https://github.com/arults/hermes-changefreeze
