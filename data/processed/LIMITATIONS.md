\# Known Limitations \& Error Analysis



Documented here as we find them — this is a running log, not a one-time task.

Being able to name your own model's weaknesses honestly is a stronger signal

in interviews than just reporting a high accuracy number.



\## 1. `uses\_https` signal is partly a dataset artifact (found after Phase 3 v1)



\*\*Observation:\*\* In the trained model's feature importance, `uses\_https` was

one of the top predictors. Investigating the raw distribution showed:

&#x20; - Legit sample (Tranco top sites): 100% use HTTPS, zero variation

&#x20; - Risky sample (phishing/scam/spam): \~51% use HTTPS, roughly a coin flip



\*\*Why this is a limitation, not just a finding:\*\* The "legit" class comes

from Tranco's \*top\* sites list — large, established, professionally-run

domains. Virtually all of them enforce HTTPS. This isn't representative of

\*all\* legitimate websites (many small/local/hobby sites still run on plain

HTTP), so the model has effectively learned "is this a top-tier popular

domain" rather than the more general "is this legitimate." The signal is

real but narrower than it appears.



\*\*Fix for v2:\*\* Diversify the legit training sample beyond just Tranco's top

N — include a broader, more "long-tail" set of legitimate but less famous

sites (e.g. small business sites, niche blogs) so the model isn't implicitly

learning "popular == legit."



\## 2. `domain\_length` appears to be a genuine, robust signal



For contrast: this one held up under investigation. Legit domains averaged

\~12 characters, risky domains averaged \~28 characters with much higher

variance — consistent with a real, known pattern (phishing URLs often embed

random IDs/verification paths into long subdomains). No action needed here,

but noting it as a validated (not just assumed) signal.



\## 3. Content analyzer alone missed a real phishing site (found after Phase 4a)



\*\*Observation:\*\* Tested against a real phishing URL from the OpenPhish dataset —

`https://www.roblox.com.bi/users/.../profile`, a lookalike domain impersonating

Roblox. The content analyzer scored it \*\*0.0 risk\*\*, a false negative.



\*\*Root cause:\*\* The content analyzer only receives the page's visible text and

title — never the URL/domain itself. This particular phishing page was a

well-made visual clone with correct branding and no textual red flags, so

there was genuinely nothing in the text alone for the model to catch. The

actual giveaway is the domain: `roblox.com.bi` is a classic typosquat/lookalike

pattern (real Roblox is `roblox.com`), which is a \*technical/structural\*

signal, not a content one.



\*\*Why this validates the project's core design, not just a bug to patch:\*\*

This is direct empirical evidence that single-signal detection has blind

spots — exactly the reasoning behind combining technical signals (Phase 3)

with content analysis (Phase 4a) in a fusion layer, rather than shipping

either one alone. The technical model's domain-structure features

(`domain\_length`, `num\_subdomains`, WHOIS age) are well-positioned to catch

this specific case where content analysis fails.



\*\*Action:\*\* Proceeding to build the reasoning/fusion agent (Phase 4b) that

combines both signal sources — this finding is the concrete justification

for why that layer is necessary, not optional.



\## 4. Fusion agent caught what content-analysis missed, but reasoning has a gap (found after Phase 4b)



\*\*Observation:\*\* Testing the same Roblox-lookalike phishing URL through the

fusion agent: technical model scored it 0.981 (high risk), content analyzer

still scored 0.0, and the fusion agent correctly output "suspicious" instead

of a false "safe" — validating the core multi-signal design (see #3 above).



\*\*But:\*\* the LLM's written explanation described the domain's age (158 days)

and valid SSL as "positive indicators," when in context they should be red

flags — a domain claiming to be an established company (Roblox, \~15+ years

old) but registered only 158 days ago is itself suspicious, not reassuring.

The model reported the correct number but drew the wrong conclusion from it.



\*\*Root cause:\*\* The fusion prompt gives the LLM raw signal values but never

tells it what brand/entity the page claims to represent, so it can't reason

about whether the domain age is plausible \*for that specific claim\*.



\*\*Fix for v2:\*\* Pass the page's apparent claimed identity (e.g. detected

brand name from title/content) into the fusion prompt, so age/SSL evidence

can be evaluated relative to the claim being made, not in isolation.



\*\*Why this is still a good result to report:\*\* the \*verdict\* was correct

(suspicious, not safe) even though one sentence of the \*explanation\* was

locally inconsistent — worth being upfront about in write-ups: fusion

improved the outcome, but reasoning quality on individual evidence points

still has room to improve.

## 5. Content-analyzer scrape failures were wrongly treated as risk evidence (found + FIXED after Phase 5 eval)

**Observation:** Initial full-pipeline evaluation (30 held-out URLs) showed
73.3% accuracy but a high false positive rate (46.7%) — nearly half of
legitimate sites were incorrectly flagged. Inspecting `eval_results.csv`
showed 6 of 7 false positives had a missing (`null`) content risk score,
meaning the page scrape had failed. Re-running the fusion agent on one case
(`mp4moviez.webcam`) showed the LLM's explanation explicitly said a scrape
failure "further raises suspicions" — treating a neutral technical failure
as if it were evidence of wrongdoing.

**Fix:** Added an explicit instruction to the fusion prompt: a null content
score means the page could not be scraped for a technical reason and must
NOT be used to justify a higher risk verdict on its own.

**Verified:** Re-ran the fix against all 7 original false positives.
`grammarly.io` immediately corrected to "safe" (95% confidence). The other 6
still landed in "suspicious"/worse, but their explanations no longer cited
the scrape failure as suspicious — instead correctly citing other technical
evidence (e.g. missing SSL, unreachable status). This is a real, confirmed
fix to a reasoning bug, not just a documented limitation.

## 6. One "false positive" turned out to be a dead domain, not a model error

**Observation:** `pvp.net` (from the Tranco "legit" list, technical model flagged
it "suspicious") was investigated as a potential remaining bug — our own code
reported it as unreachable with a DNS resolution failure. Suspected this might
be a bug in our scraper (e.g. missing browser User-Agent triggering bot
protection), so added a realistic User-Agent header to `get_redirect_chain()`
as a fix attempt.

**Investigation:** After the fix, `pvp.net` still failed to resolve. Verified
independently with `nslookup` against Google's public DNS, and by loading the
URL directly in a real browser — both confirmed `DNS_PROBE_FINISHED_NXDOMAIN`:
the domain genuinely does not resolve, for anyone, right now. This is not a
scraping/bot-protection bug at all — DNS resolution happens before HTTP
headers are even relevant, so a User-Agent fix could never have addressed it.

**Conclusion:** `pvp.net` is very likely a decommissioned domain (probably an
old Riot Games property retired after consolidating to riotgames.com) that
still shows old WHOIS registration data while serving nothing. Our pipeline's
"unreachable/suspicious" verdict was actually correct — the true error is in
treating Tranco's traffic-based "legit" label as ground truth, since Tranco
rankings can lag behind a domain's actual current status.

**Why this is worth documenting as its own finding:** it demonstrates the
importance of verifying a suspected bug against ground truth (browser + public
DNS) before assuming the code is wrong — the User-Agent fix was still a
reasonable, correct improvement to keep (it likely still helps other cases of
genuine bot-blocking), but it wasn't the explanation for this particular case.

## 7. Evidence-weighting + determinism fix improved the full pipeline (Phase 5, final)

**Observation:** After the finding #5 fix, re-running the same 30-URL eval
showed accuracy DROP from 73.3% to 60.0%, with recall collapsing from 93.3%
to 60.0% - several phishing sites with technical risk scores of 0.98+ were
now verdicted "safe." Investigating one case directly confirmed the model was
letting a benign content score (0.0) override an almost-certain technical
risk score, despite no code path that should cause that from the finding #5
fix alone.

**Root causes identified:**
  1. No `temperature` was set on the LLM calls, so identical inputs could
     produce different verdicts across separate runs - a reproducibility gap
     that made the regression hard to distinguish from genuine model behavior.
  2. The fusion prompt gave the LLM no guidance on how to weigh conflicting
     evidence, so it had no principled reason to trust a near-certain
     technical score over a clean-looking content score.

**Fix:** Set `temperature=0` on both LLM calls (content analyzer and fusion
agent) for reproducible output, and added explicit weighting guidance to the
fusion prompt: technical signals should dominate when they're strongly
confident (>=0.7 or <=0.2), since domain age/SSL history are harder for an
attacker to fake than clean page text.

**Result:** Re-ran the full 30-URL eval a third time. Accuracy improved to
80.0%, recall reached 100% (caught every phishing/scam site in the set),
precision improved to 71.4%. False positive rate held steady at 40% across
this run and the previous one - the SAME six legitimate sites were flagged
both times, which is itself a good sign: it confirms `temperature=0` made
the system reproducible as intended, rather than the FPR being noise.

**Remaining false positives, explained:** of the 6 recurring false positives,
2 are explainable by dataset/labeling issues already documented above -
`pvp.net` is a genuinely dead domain (finding #6) and `mp4moviez.webcam`'s
apparent piracy content likely shouldn't have been labeled "legit" by Tranco's
traffic-based ranking in the first place. The remaining ones (`nhk.or.jp`,
`ezviz7.com`, `dnse2.com`, `grammarly.io`) likely trace back to finding #1 -
the technical model's patterns, learned from a narrow "top sites" sample,
don't generalize perfectly to all legitimate site profiles.

## 8. Raw missing-data sentinel value leaked into LLM reasoning (found + FIXED post-deployment testing)

**Observation:** A real-world test against `https://antigravity.google/download`
(a legitimate Google product page, using Google's own custom `.google` TLD)
returned a false "likely_scam" verdict at 95% confidence. The explanation
cited "the domain age is listed as -1 days" as a red flag.

**Root cause:** `-1` is this project's internal sentinel value meaning "WHOIS
lookup failed / age unknown" (see `feature_extraction.py`). It was being
passed directly into the fusion prompt as a literal number, so the LLM
reasoned about it as if -1 were a real (nonsensical) domain age, rather than
understanding it as "we don't know." Single-word domains under company-owned
custom TLDs (like `.google`) are a legitimate, common case where standard
WHOIS lookups fail entirely - not a sign of anything suspicious.

**Fix:** Two changes to the fusion prompt: (1) missing domain age is now
rendered as the human-readable string "Unknown (WHOIS lookup failed or
returned no data)" instead of the raw -1 value, and (2) added explicit
guidance listing legitimate reasons a WHOIS lookup can fail (privacy
protection, custom TLDs, unresponsive WHOIS servers), instructing the model
not to treat unknown domain age as risk evidence by itself.

**Verified:** Re-ran the same URL after the fix. Verdict corrected to "safe"
(80% confidence), and the explanation now explicitly states the unknown
domain age "is not considered a strong evidence of risk on its own, as it
can have legitimate causes" - directly reflecting the new instruction.
Notably, the model didn't just blindly flip its verdict - the technical
score was still very high (0.969), and the earlier finding #7 rule says high
technical scores should generally dominate, but here the model correctly
recognized *why* that score was inflated (an unreliable signal) and
appropriately discounted it rather than mechanically applying the override
rule. This is a good sign of context-aware reasoning, not just prompt
patching.

**Broader lesson:** any internal sentinel/placeholder value (like -1 for
"unknown") must be translated to human-readable form before it reaches an
LLM prompt - raw placeholder values designed for code logic are not safe to
expose directly as "evidence" in natural language reasoning.