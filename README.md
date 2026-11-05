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

Checks this session: `hermes plugins validate` **passed** (security **safe**) · `doctor` **OK** (5 tools, 1 hook) · unit tests **15/15** · [Evidence](docs/EVIDENCE.md).

Local only. Nothing leaves your machine.

**[Short demo](https://github.com/arults/hermes-changefreeze/releases/download/v0.1.0-demo/changefreeze-demo.mp4)** · **[X demo](https://x.com/PostcardCrypto/status/2118326708936040613)** · [Hackathon listing](https://github.com/NousResearch/hermes-agent/pull/149474)

MIT · https://github.com/arults/hermes-changefreeze
