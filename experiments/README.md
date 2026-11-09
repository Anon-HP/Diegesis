# Experiment log

All CV numbers are out-of-fold over **dev books** (train+val splits), from StratifiedGroupKFold with 5 folds
grouped by book. Only the final run evaluated the **test books**, once. Labels are LLM-generated. See
`docs/limitations.md`.

Columns: `macroF1` = macro-F1 over the classes present in the evaluation set; `macroF1_sup` = macro-F1 over
the classes with ≥10 examples (in practice action, subject, scene); `balAcc` = balanced accuracy; `acc` = accuracy.

| Run (file) | Labels | What changed | Best config (by CV) | CV result | Conclusion |
|---|---|---|---|---|---|
| `r1_cv.json` | R1 (222 natural) | CLIP features + OCR cues + low-level stats; logreg/MLP/HGB | logreg_pca\|full | macroF1 0.293, acc 0.475 | Beats majority (0.111/0.383) but weak |
| `r1_cv_v2.json` | R1 | + DINOv2 global + patch matching | logreg\|clip+dino+match+text+low+cue | macroF1 0.299, acc 0.492 | DINOv2 adds ~nothing |
| `r2_cv.json` | R1+R2 (671) | same groups, more data | logreg_pca\|clip+dino+match+text+low+cue | macroF1 0.246, acc 0.448 | Plateau; not comparable to R1 (more classes present) |
| `r2_cv_b_ckpt/` | R1+R2 | + mean-centred cosines (`cos_c`), caption lexicon (`cue2`) | logreg_pca\|clip+dino+cos_c+…+cue2 | macroF1 0.249 | Stopped early (80/100 folds): no gain, HGB too slow |
| `r3_cv.json` | R1+R2+R3 (788) | + CLIP zero-shot shot-type attributes (`zs`); select on macroF1_sup | **logreg_pca\|clipdiff+zs+cos_c+match+low+cue2** | macroF1_sup 0.376, acc 0.414 | Every config falls within 0.33–0.38 macroF1_sup |
| `r3_cv_conf.json` | R1–R3, training on medium+high confidence only | label-noise filtering | — | macroF1_sup 0.363 | No gain |
| `r3_cv_hgb.json` | R1–R3 | gradient boosting on the compact feature set | — | macroF1_sup 0.360 | No gain |
| **`r3_cv.json` → `test`** | test books | **single held-out evaluation** of the selected config | — | **macroF1_sup 0.394 (CI 0.32–0.47), macroF1 0.236, balAcc 0.232, acc 0.375 (CI 0.31–0.46)** | Beats rules (0.304) and majority (0.174) on macroF1_sup. Accuracy is not significantly above majority (0.353) |

## Diagnostics that shaped the design (not model runs)

- **Raw vs centred similarity (AUC).** Detecting synthetic cross-book pairs: CLIP 0.84 → centred 0.95;
  DINOv2 0.75 → 0.89. Scene vs rest stays around 0.60 and action vs subject around 0.55, whatever the
  similarity measure.
- **Caption cues.** Annotators cite a caption or time cue in 83% (116/140) of scene-to-scene pairs.
  Keyword matching finds one in only 23% of them with internal Tesseract OCR, and in 34% with COMICS' Google
  Vision OCR. That reference OCR was used only for this diagnostic and for OCR tuning, never as a feature.
- **OCR tuning** (40 panels; word recall against the reference OCR). Current settings (gray, 1600 px,
  psm 11) give 0.70. Alternatives give 0.58–0.73, and Otsu binarisation adds nothing. A gain of 2 points or
  less doesn't justify re-running OCR on everything.
- **CLIP zero-shot attributes.** Best single AUC for scene vs rest is 0.67, from "a wide establishing shot
  of a city" on panel B.
- **Active mining for rare classes (round 3).** The 160 mined pairs gave 3 moment and 2 aspect labels
  (rare-class rate ≈ 4%, no better than random sampling) and 27% invalid pairs (mostly ads).
  This was ineffective.
- **Agreement between LLM annotators** (`agreement_r1.json`, `agreement_r1r2.json`). Opus vs Sonnet on
  147 doubly-labelled pairs: 75.5%, κ = 0.64. Most disagreements are action vs subject.
- **Test error analysis.** 5% of natural test pairs are falsely predicted non-sequitur (the synthetic
  shortcut). Accuracy by annotator confidence: high 0.51, medium 0.34, low 0.09. Accuracy on the
  caption-cue stratum: 0.25.

## Example predictions (`example_predictions.csv`)

The file holds 8 class-balanced test-split pairs.
- **Held-out** predictions use `models/head_dev.joblib`, which never saw the test books. They agree with
  the LLM label on 5/8 pairs.
- The deployed `models/head.joblib` was refit on all labelled pairs, test included, so its 7/8 on the same
  pairs is **in-sample** and is not evidence of accuracy.
