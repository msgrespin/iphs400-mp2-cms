# Handoff: IPHS 400 MP2 CMS, "final" phase (2026-10-03)

Repo: `/home/msgre/code/iphs400-mp2-cms` (branch `main`, GitHub `msgrespin/iphs400-mp2-cms`).
`.claude/state/phase` is set to `final` (no ticket; all required tickets are done).

## Done this session (details are in commit `b502cd2`, don't redo)
- 14 screenshots in `docs/screenshots/`: `login`, `dashboard`, `content-list`, `editor`, `users`, `editor-denied`, each as `-1280.png` and `-390.png`, plus `editor-preview-1280.png` and `editor-preview-390.png`. The checker requires the name `users`, not `accounts`.
- Root cause found: `templates/base.html` linked `style.css` relatively, so admin pages deeper than `/admin` got a 404 and no CSS. Fixed to `/style.css` and covered by `tests/test_admin_stylesheet.py`.
- 390 px overflows fixed (Accounts table wrapped in `.table-wrap`, textarea width, `td, th` set to `overflow-wrap: break-word`, all in `app/publish.py` `CSS`). Public home was already fine.
- Demo data: Post 2 ("Snack request form is open") set back to Draft. DB had 4 Accounts, 2 Posts, 3 Pages.
- User committed and pushed `b502cd2` themselves, then ran `uv run cms publish` + `uv run cms deploy` twice (gh-pages `69a72d6 -> 0e49e54 -> 040bd76`).
- Suite: 202 passed.

## Decisions and caveats worth knowing
- The editor has no live preview pane; Preview opens `/admin/posts/preview` in a new tab. User chose to capture that page separately (`editor-preview-*`), not to change the app. Rubric C5 wants "editor shows a Markdown preview", so this is a possible grading risk.
- User accepted that the Accounts table scrolls inside its box, so the "New password" and "Deactivate" columns are cut off in `users-1280.png` and `users-390.png`.
- User did not say why they deployed twice; the two gh-pages builds were never compared. Live site not yet verified (Pages can take ~10 min).
- `.gstack/` is in `.gitignore` (kept on purpose).
- Rules from `CLAUDE.md`: no new dependencies without asking (Playwright is NOT in the stack; use gstack `/browse`), no hand-editing `site/`, published HTML uses relative paths only. The user's global instructions say to make the minimum edit and list what changed after multi-file edits.
- Browser testing tip: bust the cache on pages, and note admin pages and the public site share one stylesheet.

## Remaining Stage 2 items (from `uv run python scripts/check_submission.py --stage 2`)
- FAIL: at least one handoff saved in `docs/handoff/` (this temp file does not satisfy it; the checker looks in the repo)
- FAIL: report `docs/iphs400_mp2-web-cms_report_{first}-{last}_{YYYYMMDD}.md` (1-2 pages, four questions in manual section 8.2)
- FAIL: README "Run locally" section; AI Use Statement still has the template placeholder (needs models/skills, two quoted real prompts, one real model failure, Backends used table)
- FAIL: tag `mp2-final` (only `mp2-mvp` exists)
- Open: ask the user for the live Pages URL (README "Live URL"), then verify the home page at 390 px on it.
- Source fidelity rule: for the report and README, read the manual (`docs/manual_iphs400_mp2-web-cms_20260922.md`) and rubric (`docs/mp2-grading-rubric_20260922.md`) first and don't write claims from memory.

## Suggested skills for the next agent
- `mattpocock-skills:writing-for-agents` or plain editing for README/report drafting; follow the source-fidelity rule above.
- `mattpocock-skills:code-review` (or `/code-review`) before any commit that closes a ticket, per `CLAUDE.md`.
- `browse` (gstack) for verifying the deployed site at 390 px.
- `superpowers:verification-before-completion` before claiming the checker passes.
