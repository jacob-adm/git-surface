# Documented attacks, replayed

Each row below is a published attack or study. Where the attack needed a change to a repository,
that change is rebuilt as a branch off a small `main`, and the table shows what `git surface`
reports for it. A last branch changes only application code and is not reported.

`tests/test_incidents.py` builds the same repository and checks that the output on this page is
exactly what the command prints, so the page changes when the command does.

| Source | Repository change | Branch | Reported as |
|---|---|---|---|
| Nx "s1ngularity", August 2025 [1] | A branch replacing the CI script that the publish workflow runs; the workflow ran it with the npm token | `ci-script` | `ci` (named in the workflow) and `exec` |
| Shai-Hulud, September and November 2025 [2][3] | A post-install script (first wave), or a `preinstall` script that triggers new files (second wave), in `package.json` | `install-postinstall`, `install-preinstall` | `install` with the script name, and `deps` |
| Rules File Backdoor, March 2025 [4] | Zero-width and bidirectional characters inside agent rule files | `rules-cursor`, `rules-copilot` | `agent`, and `hidden` with each code point |
| Hidden-comment injection, 2026 [5] | An instruction in an HTML comment in a skill's Markdown, which can be invisible when rendered yet reach the model | `comment-skill`, `comment-readme` | `hidden` (`<!--`), and `agent` for the skill |
| Trojan Source, 2021, CVE-2021-42574 [6] | Unicode control characters that reorder how source code is displayed | `trojan-source` | `hidden` with each code point |
| Agent dependency choices, 2026 [7] | A new dependency and a changed version | `dependency` | `deps`, naming the added package and the version change |
| (control) | Application code only | `control-app` | nothing |

The repository change is rebuilt from each source's description, with placeholder names and
`example.invalid` addresses; no attack code is included. The Nx and Shai-Hulud changes were
pushed or published with stolen credentials, not proposed for review; the branches show what
`git surface` reports when the same change reaches a branch it checks.

## Command and output

```sh
git for-each-ref --format='%(refname:short)' refs/heads/ | git surface main
```

```text
ci-script	ci	M named-in .github/workflows/publish.yml	scripts/publish.sh
ci-script	exec	M	scripts/publish.sh
comment-readme	hidden	<!-- line 2	README.md
comment-skill	agent	A	.claude/skills/format/SKILL.md
comment-skill	hidden	<!-- line 4	.claude/skills/format/SKILL.md
dependency	deps	M +evil-pkg left-pad 1.3.0->1.1.0	package.json
install-postinstall	deps	M	package.json
install-postinstall	install	M scripts.postinstall	package.json
install-preinstall	deps	M	package.json
install-preinstall	install	M scripts.preinstall	package.json
rules-copilot	agent	A	.github/copilot-instructions.md
rules-copilot	hidden	U+202E line 1	.github/copilot-instructions.md
rules-cursor	agent	A	.cursor/rules/html.mdc
rules-cursor	hidden	U+200B line 1	.cursor/rules/html.mdc
rules-cursor	hidden	U+200D line 1	.cursor/rules/html.mdc
trojan-source	hidden	U+202E line 2	src/app.py
trojan-source	hidden	U+2066 line 2	src/app.py
```

`main` and `control-app` print nothing. The command exits 1 because it reported something.

## What these attacks also did that git surface cannot see

`git surface` reads branches. Parts of the same attacks never touched one:

- **Text in an issue or pull request.** In the GitHub MCP issue injection [8] the instruction was
  in a public issue, and in Nx [1] the first step was a pull request title containing shell
  commands, run by a `pull_request_target` workflow.
  Neither is a file on a branch. The change an agent makes after reading such text is reported
  when it touches a reported class.
- **Code inside a published release.** Shai-Hulud changed packages on npm. A branch that pins an
  affected version shows only as a `deps` version change; whether that version is malicious is not
  known from the repository. Release changes between versions are what
  [release-drift](https://github.com/jacob-adm/release-drift) reports.
- **Whether a version is vulnerable.** The `dependency` row names the added package and the
  version change; it does not look up advisories.
- **Data in ordinary files.** A branch that copies private data into application code or prose
  is not reported, as in [8], where the result was a pull request with private details.
- **The new file itself.** `bundle.js` and `setup_bun.js` are not reported on their own; the
  `install` line that runs them is.

See [Limitations and security](limitations-and-security.md) for the rules that decide what is
reported.

## Sources

1. Nx, "S1ngularity - What Happened, How We Responded, What We Learned", September 2025:
   https://nx.dev/blog/s1ngularity-postmortem
2. Palo Alto Networks Unit 42, ""Shai-Hulud" Worm Compromises npm Ecosystem in Supply Chain Attack":
   https://unit42.paloaltonetworks.com/npm-supply-chain-attack/
3. Datadog Security Labs, "The Shai-Hulud 2.0 npm worm: analysis, and what you need to know":
   https://securitylabs.datadoghq.com/articles/shai-hulud-2.0-npm-worm/
4. Pillar Security's "Rules File Backdoor" report, as described by The Hacker News, March 2025:
   https://thehackernews.com/2025/03/new-rules-file-backdoor-attack-lets.html
5. "When Skills Lie: Hidden-Comment Injection in LLM Agents", arXiv:2602.10498:
   https://arxiv.org/abs/2602.10498
6. N. Boucher and R. Anderson, "Trojan Source: Invisible Vulnerabilities", USENIX Security 2023:
   https://trojansource.codes/
7. "Understanding Security Risks of AI Agents' Dependency Updates" (v1; v2 is titled "Towards a
   Benchmark for Dependency Decision-Making"), arXiv:2601.00205. It reports agents selecting
   known-vulnerable versions more often than humans (2.46% vs. 1.64%):
   https://arxiv.org/abs/2601.00205
8. Invariant Labs, "GitHub MCP Exploited: Accessing private repositories via MCP":
   https://invariantlabs.ai/blog/mcp-github-vulnerability
