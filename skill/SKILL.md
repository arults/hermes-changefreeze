---
name: changefreeze
description: Quiet window so Hermes asks before it ships code.
---

# ChangeFreeze

An AI helper can ship code at a bad time and break something that is live.

You set a quiet window. During that window, Hermes asks you before it ships. Everyday work still runs. When the window ends, shipping continues again.

You end the window with `/freeze off`. You let one ship through with `/freeze allow-once`. The helper cannot end the window, shorten it, or allow a ship by itself.

Hermes also reads code cells. A cell that contains a ship command written out, including `subprocess.run(["git", "push"])`, is asked about first. A command built from pieces can still get through. This is not a sealed box.

Install: `hermes plugins install arults/hermes-changefreeze --enable`

Short demo: https://github.com/arults/hermes-changefreeze/releases/download/v0.1.0-demo/changefreeze-demo.mp4

Project: https://github.com/arults/hermes-changefreeze
