# Limitations

These limitations are real and they bound every number this project reports. Please read them
before you rely on any prediction.

## 0. Headline: a working pipeline, but a weak classifier
- On 136 held-out natural pairs from 31 unseen books, macro-F1 over action, subject and scene is
  **0.394** (95% book-bootstrap CI 0.32–0.47), against 0.174 for the majority class and 0.304 for the rule baseline.
- **Accuracy is 0.375 (CI 0.31–0.46). That is not significantly better than always answering
  "action-to-action" (0.353).** The model's value is that it spreads its predictions across classes
  sensibly, not that it is usually right.
- Per-class test F1: action 0.52, scene 0.36, subject 0.31. It got **zero** of the 3 moment-to-moment
  and the 1 aspect-to-aspect test pairs right. Natural non-sequiturs: none in the test split, and 1 in
  the whole dataset.
- On the deployed `models/head.joblib`: it was refit on all labelled pairs, test included. Any prediction
  it makes on a labelled pair is in-sample. Use `models/head_dev.joblib` to reproduce held-out behaviour.

## 1. The labels are machine-generated, not human ground truth
- There is no public dataset of originally-English Western comics labelled with McCloud's six transitions.
  Iyyer et al.'s 250 annotated pairs were never released, and they used a different five-class scheme.
- Every natural label in `data/manifest.csv` currently has `label_source=llm`. Each was assigned by a
  Claude model that viewed the two panels and followed `docs/annotation_guidelines.md`.
- **Consequence:** every evaluation number measures agreement with the LLM annotator, not
  correctness against human judgement. The classifier is in effect a small, fast, local model
  distilled from an LLM's judgement.
- Two independent LLM annotators (Opus and Sonnet) agree on about 75% of pairs (κ ≈ 0.63). This is
  similar to the human–human κ = 0.605 Iyyer et al. report for their related scheme. It shows that the
  labels are noisy and that the task is ambiguous, especially action-to-action vs subject-to-subject.
- **To fix:** have people label or verify pairs with `scripts/make_human_annotation_page.py`, which
  hides the LLM label by default. Save the CSVs to `annotations/human/`, then re-run `build_manifest.py`
  and `train.py`. Human labels automatically take precedence and are tracked as `label_source=human`.
  A human-labelled test split is the single most valuable improvement.

## 2. The rare classes are barely supported
- Golden Age American comics almost never use aspect-to-aspect or non-sequitur transitions.
  McCloud himself reports that American mainstream comics rely almost entirely on action-, subject-
  and scene-to-scene transitions. Moment-to-moment is also uncommon.
- Natural non-sequiturs: **zero** were found. The only non-sequitur training signal is
  **synthetic**: two panels taken from different books. These pairs differ in art style as well as
  content, so the model may learn "different art style ⇒ non-sequitur". **This was confirmed on
  the test set.** 7 of 136 natural test pairs (5%) were wrongly predicted non-sequitur. All were real
  subject- or scene-changes that just look very different. Treat any `non-sequitur` output as
  unreliable.
- Active mining did not fix the imbalance. A targeted round of 160 pairs, chosen as likely moment or
  aspect transitions, gave only 3 moment and 2 aspect labels, no better than random sampling.
- Aspect-to-aspect and moment-to-moment have only a handful of examples. Their per-class metrics are
  very noisy or undefined, and the model rarely predicts them.
- Macro-F1 is reported over the classes **present** in the evaluation set, with the all-six variant
  alongside it, so that absent classes neither inflate nor silently deflate the score.

## 3. Domain coverage
- Only US Golden Age comics (1938–1954, from COMICS / Digital Comic Museum) were used, and only the
  204 books in the first 3.5 GB of the archive. Modern Western comics (different art, lettering,
  colouring and pacing) are out of distribution. Expect lower accuracy on them.
- Panel order within a page comes from the COMICS authors' automatic pipeline. A few sampled pairs
  were non-consecutive or bad crops. Annotators marked these invalid, but some undetected errors may
  remain in unlabelled data.

## 4. Model and features
- The model sees only global image embeddings (CLIP ViT-B/16; DINOv2 optional), coarse patch-matching
  statistics and noisy OCR cues. It does not truly read the dialogue or understand the story.
  Transitions that depend on narrative meaning are beyond it, for example a cut that is a scene change
  only because of what a caption says, when the OCR misreads the caption.
- Tesseract OCR on hand-lettered all-caps text is noisy: it recovers about 70% of the words the Google
  Vision OCR does. Annotators cite a caption in 83% of scene changes, but keyword matching on our OCR
  finds a cue in only 23% of them. Accordingly, test accuracy on the caption-cue stratum is only 0.25.
- OCR adds about 3–10 s of CPU time per panel at inference.

## 5. Evaluation
- Splits are by book, so no book contributes pairs to both the training and test splits. With about
  200 books, the test split has a few dozen books and on the order of a hundred labelled pairs,
  so its confidence intervals are wide.
- Some sampling strata deliberately over-represent rarer situations (caption cues, cross-page,
  similarity extremes, active mining). Metrics on the `random` stratum are reported separately,
  because only that stratum reflects the natural class distribution.
