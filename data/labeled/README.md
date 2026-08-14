# Scam/Spam Seed Dataset

There's no clean public dataset for "spam/scam but not phishing" (SEO spam, fake
shops, content farms, dropshipping scams) — this is the gap this project fills.
This file is a template for you to build that dataset yourself.

## Columns
- `url` — the site URL
- `label` — always `spam` or `scam` for this file
- `category` — one of: `seo_spam`, `fake_shop`, `content_farm`, `fake_reviews`, `other`
- `notes` — why you flagged it (useful later for writing eval error analysis)

## How to source examples safely

**Do NOT browse to live scam/fake-shop sites directly** — some redirect to malware
or unsafe payloads. Safer sources:

1. **Scam-tracking communities/reports** — sites like scamadviser.com, Trustpilot's
   "flagged" reports, or r/scams often *document* scam URLs with screenshots
   without you needing to visit the live site.
2. **Google Safe Browsing transparency report** — lets you check a URL's status
   without visiting it.
3. **Archived snapshots** — web.archive.org lets you view a cached version, which
   is generally safer than the live (possibly currently-serving-malware) site.
4. **SEO spam** is usually safer to browse directly since it's low-quality content
   farms rather than malicious payloads (still, use a sandboxed browser/VM if unsure).

## Target size

Aim for 80-150 rows across categories for a usable v1 eval set. It doesn't need
to be huge — even 100 well-labeled examples gives you a real, defensible
precision/recall number, which is the point.
