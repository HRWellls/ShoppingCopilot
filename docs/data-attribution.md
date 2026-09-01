# Data and Asset Attribution

Shopping Copilot uses the competition package derived from **Amazon Reviews 2023**, published by McAuley Lab at UCSD.

- Source project: <https://amazon-reviews-2023.github.io/>
- Selected category: `Clothing_Shoes_and_Jewelry`
- Product join key: `parent_asin`
- Modality used: text and structured product metadata only
- Competition catalog: 50,000 read-only products
- Public development set: 200 labeled sessions
- Private final evaluation: organizer-controlled and not included

The repository does not publish raw reviews, user identifiers, timestamps, purchase histories, account credentials, private organizer labels, private holdout sessions, model caches or API keys. The full catalog is intentionally ignored and must be acquired through the organizer-provided participant kit/release path.

The underlying Amazon-derived content remains subject to the source dataset's applicable terms. This project does not claim ownership of that content. The public browser demo uses only a small text/metadata catalog fixture and does not use third-party product images, videos or logos.

`data/sample_smoke.jsonl` contains four project-authored synthetic sessions used
only to verify execution against the 100-row sample. Its output is not reported
as a competition quality result.

Generated diagrams and UI elements in this repository are original project assets. The public demo video URL will be added to README and Devpost after upload.
