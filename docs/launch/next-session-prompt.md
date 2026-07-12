# Next-session prompt (roast the launch, then post)

Paste this into a fresh Fable session (after /clear) to finish the launch.

---

You are continuing the fintech-roast project. Repo: /Users/dylanmerigaud/Code/fintech-roast
(GitHub DylanMerigaud/fintech-roast). Two launch drafts are already written and committed at
docs/launch/show-hn.md (Show HN) and docs/launch/blog-post.md (long-form for dev.to and
Medium). A real concurrency bug was filed on Medusa as issue #16012; two field reports and
the evals are in the repo. Author's writing style bans: em-dashes and en-dashes, "not just X
but Y", rule-of-three padding, "delve / leverage / robust / seamless / elevate", hedging
stacks, AI-sounding transitions. Keep everything plain-ASCII.

Do this in order:

1. ADVERSARIAL ROAST. Read both drafts and the repo context (README.md, eval/FIELD-REPORT-2.md,
   eval/RESULTS.md, rules/). Attack the drafts like a hostile Hacker News commenter AND a
   sharp copy editor. Find: the weakest of the three titles, the single line a skeptic
   destroys first (self-planted evals / "it is just Claude with a prompt" / "you found ONE
   bug" / "filed but not accepted yet"), and any sentence that reads as LLM-generated. Be
   brutal, every criticism must be actionable. Fact-check every number against the repo
   (rules count 41, domains 10, cold-scan recall 86%, Medusa 16 emitted / 4 confirmed / 10
   refuted, issue #16012). Consider running this critique as an adversarial subagent, the
   same posture the tool itself uses.

2. APPLY THE FIXES to both files: pick the strongest title, tighten, cut dead weight, fix
   anything that sounds like AI or that a skeptic wins on. Keep the honest limits intact
   (self-planted evals, verifier is adversarial not human, one field report is anonymized
   and not reproducible, the Medusa issue is FILED not accepted). Commit and push.

3. POST, per what each platform actually allows. Do NOT treat these the same:
   - HACKER NEWS: no post API, and scripted submission is against its rules (risks the post
     being killed and the account flagged). DO NOT auto-submit. Instead print the final
     title + body + first-comment and pbcopy the body, with the exact manual steps
     (https://news.ycombinator.com/submit, paste title + text, submit, then post the
     first-comment). This click is the human's.
   - DEV.TO: has an official Forem Articles API. Check env for a key (DEV_API_KEY or
     DEVTO_API_KEY); if absent, ask the user for one or prepare a manual paste. With a key,
     publish the long-form draft: POST https://dev.to/api/articles with header
     "api-key: <key>", JSON {"article": {"title": ..., "body_markdown": ...,
     "published": true, "tags": ["ai","fintech","codereview","typescript"],
     "canonical_url": "https://github.com/DylanMerigaud/fintech-roast"}}. This is a
     documented feature, not reverse-engineering. (Use "published": false to stage a draft
     for the user to click live, if they prefer.)
   - MEDIUM: its publishing API is effectively deprecated (no new integration tokens).
     Prepare the long-form for manual paste at https://medium.com/new-story; do not attempt
     an API post unless the user hands you a working token.

4. Report exactly what you posted (with URLs) and what you left for the human to click.

---
