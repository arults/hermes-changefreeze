<p align="center">
  <img src="docs/assets/hero.jpg" alt="Calm dawn over a quiet pier" width="100%" />
</p>

# ChangeFreeze

**Problem.** An AI helper can ship code while people are using the live product — and break what they see.

**Fix.** You set a quiet window. In that window Hermes **asks you before it ships**. Everyday work still runs. When the window ends, shipping continues.

<img src="docs/assets/how-it-works.jpg" alt="Quiet window → ask before shipping → everyday work continues" width="100%" />

1. Set the quiet hours.  
2. Hermes asks before shipping in those hours.  
3. Chat and planning keep working.

### Good to know

You start a window with no end time by typing `/freeze on`. You set an end time with `/freeze until`. You end the window with `/freeze off`. You let one ship through with `/freeze allow-once` and the command.

The ChangeFreeze tools the helper can call cannot turn that window off, make it shorter, or allow a ship. You do those.

That is not the whole story. If the helper can edit files or run a shell command, it can change the saved `state.json` or `allowlist.json` and undo the window that way. This plugin does not block those edits.

Hermes reads the text of the terminal command and the text of a code cell. If a ship command is written there — in one piece, or as quoted words the way Python's subprocess does — Hermes asks you first. A code cell that says `subprocess.run(["git", "push"])` is one of those.

If the words are built from pieces, encoded, or hidden, this check does not see them. It is a text check, not a sandbox. `git -C <dir> push` and `git -c <opt> push` are also missed.

### Example from a real run

```text
Quiet window ON
  try to ship code  →  Hermes asks you first
  everyday command  →  allowed
Quiet window OFF   →  shipping continues
```

<img src="docs/assets/proof.jpg" alt="Proof from a live run: quiet window on, ship attempt, Hermes asks first" width="100%" />

### Try it

```bash
hermes plugins install arults/hermes-changefreeze --enable
```

Pin the reviewed SHA from the [hackathon listing](https://github.com/NousResearch/hermes-agent/pull/149474) when you want a frozen tip.

What this revision was checked with is in [Evidence](docs/EVIDENCE.md).

Local only. Nothing leaves your machine.

**[Short demo](https://github.com/arults/hermes-changefreeze/releases/download/v0.1.0-demo/changefreeze-demo.mp4)** · **[X demo](https://x.com/PostcardCrypto/status/2118326708936040613)** · [Hackathon listing](https://github.com/NousResearch/hermes-agent/pull/149474)

MIT · https://github.com/arults/hermes-changefreeze
