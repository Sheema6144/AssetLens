# Search quality: analysis

This file explains **how search quality was checked** and **where it works or fails**. The raw per-query results (top-5 files, scores, ✓/✗ judgments) are in [RESULTS.md](RESULTS.md), exported from the app's Evaluate tab.

## Method

1. **14 test queries** (`eval/queries.json`). They cover all three media types, the five example queries from the brief, and four queries *designed to expose known weaknesses*: fine-grained colour, counting, floor plans, and the "testimonial" concept.
2. **Expected assets** were defined before looking at results, using the download manifest (`data/dataset_manifest.csv` records the topic each file was fetched for). Files have neutral names (`pixabay_img_123.jpg`), so the search cannot use filename hints.
3. **Judging.** Every top-5 result was opened and marked ✓ or ✗ by hand in the Evaluate tab. The rule: ✓ if a normal user typing that query would be happy to get this result.
4. **Metrics:**
   - **Precision@5:** share of the top 5 that is relevant.
   - **MRR:** 1 / rank of the first relevant result.
   - **Hit-rate@5:** at least one good result in the top 5.
   - **Recall@10:** relevant assets found in the top 10, out of all assets ever judged relevant for that query.

## Final numbers (1.5 GB, 900 unique assets, all 14 queries judged)

| Metric | Value |
|---|---|
| Mean Precision@5 | **0.886** |
| Mean Reciprocal Rank | **0.916** |
| Hit-rate@5 | **1.0** (every query had a relevant result in the top 5) |
| Mean Recall@10 | **0.976** |
| Search latency (CPU, warm models) | ~0.3–0.8 s typical |

## What the evaluation changed (before → after)

The first evaluation round found two ranking bugs, which were fixed in code:

| Query | Problem found | Fix | P@5 before → after |
|---|---|---|---|
| *customer testimonial videos* | Long US congressional-hearing PDFs ranked #1–3: semantically, *"testimony"* ≈ *"testimonial"*. The "videos" intent boost (+1.0) was too weak. | Named type now gets +1.5 and other types −0.5 (still a soft preference, not a hard filter). | 0.4 → **0.8** |
| *brochures related to residential projects* | 40–300-page government PDFs beat short housing brochures, because the PDF score was the **max over hundreds of chunks**: a long document almost always has *one* chunk that matches. | A PDF's text score = average of (best chunk, whole-document summary), so the document must be **about** the topic. | 0.2 → **0.6** |

## Per-query observations

| # | Query | P@5 | Observation |
|---|---|---|---|
| 1 | a woman standing with a cat | 1.0 | Strong. CLIP + BLIP captions ("a woman holding a cat in her arms") both agree. "Standing" is ignored; sitting and holding poses also appear, which users accept. |
| 2 | customer testimonial videos | 0.8 | The dataset has **no real customer testimonials**: stock videos are silent. Results are talking-head interview videos found by the "person talking to camera" frames and Whisper transcripts. One hearing PDF still enters at rank 4. With real testimonial videos, the speech transcript would make this much stronger. |
| 3 | brochures related to residential projects | 0.6 | Housing brochures (Green Meadows, Riverside Township) and a housing-history document rank high. **Failure:** the *BuildRight Construction* brochure is #1 because its text literally says "residential and commercial projects". Text similarity cannot tell "a builder that does residential work" from "a residential project". A reranker or document-type classifier would fix this. |
| 4 | images showing a modern living room | 1.0 | Excellent. The type word "images" is detected and removed before embedding. |
| 5 | videos containing construction activity | 1.0 | Scene-aware keyframes work. Each result shows the matching **timestamp** (e.g. 12 s) and the player opens there. |
| 6 | people in a business meeting | 1.0 | Excellent. |
| 7 | aerial view of a city at night | 1.0 | Images **and** videos are mixed correctly in one ranking (z-score fusion makes them comparable). |
| 8 | food served on a table | 1.0 | Generated restaurant brochure is also found via its cover image. |
| 9 | a dog playing outdoors | 1.0 | Good. Snow, grass and field scenes are all found. |
| 10 | beach at sunset | 1.0 | Excellent. Includes a video matched at 34 s. |
| 11 | apartment floor plan | low | **Weakest query.** Only one true floor-plan image exists in the index, because the Wikimedia floor-plan PDFs failed to download (HTTP errors). The system returns that blueprint at #1, then "apartment" interiors. Lesson: **retrieval cannot return what is not in the collection**. Recall depends on the dataset. Also, CLIP ViT-B/32 is weak on line drawings; OCR on images or a document-layout model would help. |
| 12 | construction site photos | 1.0 | Type intent "photos" correctly ranks construction **images** above the construction **videos** that dominate query 5. |
| 13 | a red car parked on the street | 0.6 | Colour + object work well (all 5 are red cars). **Failure:** ranks 1–2 are headlight close-ups where no street is visible, yet BLIP *hallucinated* "parked on the side of a road". Caption errors are amplified because captions feed the text signal. |
| 14 | two cats sleeping together | 0.4 | Known **CLIP limitation: counting and actions**. "Two cats" is understood, "sleeping" is often ignored: two cats *sitting* at a window rank #3–4. A VLM reranker over the top-20 would fix this. |

## Summary of weaknesses → next steps

| Weakness | Evidence | Next step |
|---|---|---|
| Fine attributes / actions / counting | Q13, Q14 | Re-rank the top-20 with a vision-language model (Florence-2, Qwen-VL) or a larger SigLIP model on GPU |
| Caption hallucination | Q13 | Weight captions lower when CLIP disagrees; use a stronger captioner |
| Lexical-semantic near-misses in documents | Q2 (testimony), Q3 (builder brochure) | Cross-encoder reranker on the top-20 text hits; document-type classification |
| Dataset coverage | Q2 (no real testimonials), Q11 (few floor plans) | Larger, curated collection; the indexer already scales incrementally |
| Small judged set (14 queries × 5) | — | Grow to 50+ queries; log user clicks as implicit relevance feedback |
