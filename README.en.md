# x-follow-cleaner

English | [中文](README.md)

A toolkit for cleaning up your X (Twitter) following list. Once you follow a few thousand accounts, the real question is not "who should I remove" — it is **"is this account still worth a slot in my timeline?"**

Core principle: **unfollowing is irreversible, so a wrongful unfollow is far worse than a missed one.** Every design decision here optimizes for driving the false-positive rate to zero.

---

## Results (reproducible)

```bash
python3 run_tests.py
```

| Check | Result |
|---|---|
| Labelled samples (32, incl. 8 adversarial) | Accuracy **100%**, wrongful unfollows **0**, misses **0** |
| vs. naive rules (how typical tools work) | Baseline **5 wrong / 29.4%** → this engine **0 / 0%**, recall 100% for both |
| Scale test (2,000 simulated accounts) | Wrongful unfollow rate **0.00%**, recall **76.7%**, 22.8% flagged for removal |
| Engine parity | Python and browser engines produce **identical scores** on all 32 cases |

> On the 100%: grading yourself on your own exam invites overfitting, so two extra safeguards are in place —
> ① a **naive baseline rule set** (blanket +35 on marketing keywords, all badges treated as authoritative, old accounts always rewarded) is benchmarked against, and the delta is what proves the improvement is real;
> ② a **2,000-account scale test** shows the result does not hinge on 32 hand-picked cases.
> The scale test is a simulator. Judgement on your own data should come from your exported `following_audit.json`.

---

## Scoring framework

In order of importance:

1. **Content quality** — not reducible to "how long since the last post"
2. How much it is **followed by people who matter** (social proof / reputation)
3. Whether it is heavy on **promotion / marketing / scams**
4. Whether it is **AI-generated / automated**
5. Whether it **follows far too many accounts**
6. Whether it **follows you back** — last

Interpreting the score: **higher = more deserving of removal; negative = keep.** Default threshold is 20.

### Five anti-false-positive designs (v3)

| # | Problem | Fix |
|---|---|---|
| A | `link in bio`, `linktr.ee`, `推广`, `带货` are used by legitimate creators too; a blanket +35 kills them | Marketing keywords are **tiered**: HARD (scam/black-market) +35, SOFT (commercial) +12 |
| B | "Crypto researcher, ex-JP Morgan" getting deleted as a scam account | **Credible-identity discount**: professors / journalists / engineers / OSS authors get a 70% reduction on marketing hits |
| C | By 2026 the blue badge is a paid subscription anyone can buy; it is no longer an authority signal | Badges are **tiered**: legacy/business/government −25, paid blue only −5 |
| D | A product designer with 3,100 following / 900 followers labelled a follow-back spammer | Follow ratio uses **two conditions**: ratio *and* absolute following count, in tiers |
| E | Bulk accounts carry no obvious keywords | **Random-digit-suffix handle** detection (5+ trailing digits) |

One deliberate extra: **degraded-account detection.** The accounts most worth removing are often not obvious junk — they were good when you followed them and degraded later. Old account, real followers, every structural signal normal; only current behaviour gives them away. In a typical tool, "old account −10" cancels out "marketing +35", landing at 20 and letting the worst offender through. This engine drops the old-account bonus when marketing hits, and adds "★degraded old account" +10 instead.

---

## Files

| File | Purpose |
|---|---|
| `x_smart_unfollow.js` | **One-shot (recommended)** — paste into the following page; scores and unfollows as it scrolls |
| `x_audit.js` | Read-only audit: export the full following list to JSON, deletes nobody |
| `x_deepscan.js` | Deep data: per-profile followers / following / badge type / tweet count (Tampermonkey userscript) |
| `x_score.py` | Report path: full scoring + checkable HTML report + unfollow list |
| `x_unfollow.js` | Unfollow from an explicit handle list |
| `testcases.json` | 32 labelled samples (ground truth), incl. 8 adversarial cases |
| `benchmark.py` | Head-to-head against the naive baseline |
| `stress_test.py` | 2,000-account scale test |
| `verify_sync.py` + `engines_check.js` | Engine parity check |
| `run_tests.py` | Runs every check at once |
| `x_guide.html` | Illustrated usage guide |
| `competitive_analysis.html` | Competitive analysis |

---

## Quick start

**Path 1: one-shot (recommended)**

1. Open `https://x.com/<your-handle>/following`
2. Press `Cmd+Option+J`, paste the entire contents of `x_smart_unfollow.js`, hit Enter
3. `DRY_RUN = true` by default — review whether the verdicts match your intuition first
4. Once satisfied, set `DRY_RUN = false` and run again

The four knobs at the top of the file:

```js
const DRY_RUN   = true;    // preview first
const MIN_SCORE = 20;      // raise to 40 to cut only the worst offenders
const WHITELIST = [];      // handles that must never be touched — highest priority
const WEIGHTS   = {...};   // the framework is yours: negative = keep, positive = remove
```

**Path 2: report (when you want to pick carefully)**

```bash
# 1. Run x_audit.js in the browser to export following_audit.json
# 2. (Optional) run x_deepscan.js to fill in deep data -> deepscan.json
# 3.
python3 x_score.py                 # generates following_report.html + unfollow_targets.txt
python3 x_score.py --selftest      # check how the engine behaves first
```

---

## Safety (read this)

- **≤100 per day, spread across days, ≤50 per batch.** Manually removing 200+ in one go is usually fine, but do not keep that rate up.
- The script sleeps **15–40 seconds between actions, randomized**, to mimic the jitter of a human hand and avoid uniform-cadence detection.
- Progress is checkpointed in localStorage — interrupting a 3,000-account run does not mean starting over.
- Every run exports `cleanup_log.json` so **wrongful unfollows can be reversed**.
- X's limits are often applied retroactively. On any "action restricted" notice, stop for 48 hours.

---

## How it differs from the alternatives

Benchmarked against Circleboom (Trustpilot 2.2/5), Fedica, and assorted browser extensions.

Where this wins:
- **Explainable** — every verdict prints a score and its reasons. Circleboom is widely complained about for "90% of the not-following-back list was actually following me, so I unfollowed a bunch of people who followed me." That is the cost of a black box.
- **Open weights** — `WEIGHTS` is fully editable. You cannot change a competitor's criteria.
- **Quantified false-positive rate** — `benchmark.py` produces the comparative evidence directly.
- **Zero cost, zero data egress** — runs entirely locally; no OAuth grant to any third party.

Where it loses (honestly):
- **Execution safety** — Circleboom goes through the official API and is sanctioned by X; this is a browser script simulating clicks, which is inherently riskier and can only be mitigated by delays and batching.
- **UI** — they have mature SaaS dashboards; this is a script plus an HTML report.

---

## Known limitations

- Framework dimensions 1 (content quality) and 2 (followed by whom) can only be **settled by human eyes**. The script does the first-pass filter; of the remaining "real people who follow back", eyeballing 20 teaches you more than auto-scanning 2,000.
- The following page itself does not expose follower count, following count, or badge type — `x_deepscan.js` is needed to fill those in. The report states data coverage explicitly when it drops below 60%.
- The keyword lists lean toward common Chinese and English spam. Other languages need entries in `keywords.json`.

---

## Customization

Drop a `keywords.json` in the same directory:

```json
{
  "spam": ["jargon from your industry", "name of a specific scam"],
  "keep": ["a peer's name", "an institution you must keep"]
}
```

To retune, edit `WEIGHTS` directly. Afterwards run `python3 run_tests.py` to confirm you have not pushed the false-positive rate back up.

## License

MIT
