# Examiner demonstration guide

The guide gives an ordered sequence of real panel pairs, each run through the actual trained model.
Every label, prediction and confidence below was produced by `scripts/prepare_demo.py` on 2026-11-09.
The raw output is in `demo/demo_predictions.csv`. Re-run that script to reproduce or refresh the numbers.

## Read this first: what the numbers mean

- **"Reference label"** is the label our annotation pipeline assigned. It came from a Claude model
  following `docs/annotation_guidelines.md`. It is **not** a human-verified ground truth (see `docs/limitations.md`).
- **Deployed model** (`models/head.joblib`) is what the web app and `predict.py` use. It was refit on
  all labelled pairs, *including the test books*, so on the pairs below it is partly reciting what
  it was trained on.
- **Held-out model** (`models/head_dev.joblib`) is the identical configuration trained **without** the
  test books. Its column is the honest one for pairs from test books.
- **Location format:** "COMICS book id / page index / panel index". This is how the COMICS dataset
  numbers panels: page index 0 is the cover, and panel indices start at 0 in COMICS' reading order.
  Titles and issue numbers were read from each book's own cover image. Where the cover crop does not
  show them, the table says so; nothing is guessed.

## Demonstration sequence

| Step | Transition (reference) | Comic (from cover) | Book / page / panels | Split | Deployed: prediction (confidence) | Held-out: prediction (confidence) |
|---|---|---|---|---|---|---|
| 1 | Action-to-action | *Exciting Comics* No. 5 | 1094 / p35 / 0→1 | test | action-to-action **(0.85)** ✔ | action-to-action **(0.88)** ✔ |
| 2 | Subject-to-subject | *Smash Comics* No. 33 (May) | 2438 / p26 / 2→3 | test | subject-to-subject **(0.94)** ✔ | subject-to-subject **(0.54)** ✔ |
| 3 | Scene-to-scene | title not visible on cover crop ("In this issue: Police Dragnet traps the Phantom Fingerman"; Matt Baker cover) | 262 / p6 / 4→5 | test | scene-to-scene **(0.89)** ✔ | scene-to-scene **(0.77)** ✔ |
| 4 | Action-to-action | *Exciting Comics* No. 5 | 1094 / p24 / 1→2 | test | action-to-action **(0.88)** ✔ | action-to-action **(0.81)** ✔ |
| 5 | Subject-to-subject | *Planet Comics* No. 6 (June) | 2206 / p63 / 6→7 | test | subject-to-subject **(0.61)** ✔ | subject-to-subject **(0.63)** ✔ |
| 6 | Aspect-to-aspect | "…te Hale Western", Apr., No. 8? (title and last digit partly cut off) | 1943 / p3 / 3→4 | test | aspect-to-aspect (0.99) ✔ *in-sample* | subject-to-subject (0.46) ✘ |
| 7 | Moment-to-moment | *Jumbo Comics* (issue number cut off; "…35" visible) | 3637 / p31 / 2→3 | **train** | moment-to-moment (1.00) ✔ *in-sample* | moment-to-moment (1.00) ✔ *in-sample* |
| 8 | Subject-to-subject (failure case) | *Authentic Police Cases* (issue not visible) | 282 / p7 / 7 → p8 / 0 | test | subject-to-subject (0.41) | **non-sequitur (0.77)** ✘ |
| — | Non-sequitur | **no reliable example exists** | — | — | — | — |

### What to say at each step
1. **Action-to-action, Exciting Comics No. 5.** The hero leaps on Gage at his desk ("We're both
   starting from scratch now, Gage!"). Next, Gage has drawn a gun as the two men lock in combat. It is
   one struggle in two stages. The held-out model is 88% confident on a book it never saw.
2. **Subject-to-subject, Smash Comics No. 33.** The flaming "skeleton ghost" demands surrender; the
   next panel cuts to the villain's face as he refuses. Same scene, the focus moves to another
   participant.
3. **Scene-to-scene (book 262).** A black-market chicken deal, then a car arriving at a villa outside
   Rome. The caption ("…a beautiful German blonde whose showplace villa was just outside Rome") marks
   the jump in place and time.
4. **Action-to-action, Exciting Comics No. 5.** He punches one gangster, then grabs another as a shield.
5. **Subject-to-subject, Planet Comics No. 6.** A rocket zooms away; "a moment later, Nelson Cole
   approaches another ship". Similar confidence from both models (about 0.6). This shows a
   less-certain correct case.
6. **Aspect-to-aspect, rare class.** A train depot, then a montage of closed shops ("…everywhere,
   business is at a standstill"): different facets of one idea, with no event progressing. **Be
   candid:** the deployed model gets it right only because this pair was in its training data. The
   held-out model calls it subject-to-subject. The model has not learned aspect-to-aspect: there are
   only 4 examples in the whole dataset.
7. **Moment-to-moment, rare class.** The same frightened woman a split second later, stammering
   "M-my…" then "M-misery…". It is a textbook example, but it comes from a *training* book, so the
   result shows only what the model memorised. No moment-to-moment test pair was classified
   correctly by the held-out model (0 of 3).
8. **A known failure.** It shows the main weakness. Panel A is a close-up of a hand holding a
   hypodermic. Panel B, on the next page, is the drugged hero's dream montage of faces. The reference
   label is subject-to-subject, which is itself debatable. The held-out model calls the pair a
   *non-sequitur* with 77% confidence. Non-sequitur was learned almost
   entirely from synthetic pairs (panels from two different books), so the model over-calls it
   whenever two panels look very different. The web app shows a warning whenever it predicts
   non-sequitur.

### Categories without a reliable example
- **Non-sequitur:** the dataset has exactly **one** natural example, a gag page in a *training* book
  (2600 / p42 / 3→4, low annotator confidence). It is not a fair demonstration. Do not claim the
  model can detect real non-sequiturs.
- **Aspect-to-aspect and moment-to-moment:** there is **no correctly classified held-out example**.
  Steps 6 and 7 are shown openly as in-sample demonstrations.

## Running the demo

1. Start the backend: `.venv/bin/python serve.py`. Wait for "Application startup complete", about 20 s
   while the models load.
2. Start the frontend in a second terminal: `cd frontend && pnpm start` (after a one-time
   `pnpm install && pnpm build`). Open <http://localhost:3000>.
3. Prepare the images with `.venv/bin/python scripts/prepare_demo.py`. This copies each pair to
   `demo/NN_<pair>_A.jpg` and `demo/NN_<pair>_B.jpg` and re-checks the predictions above.
4. For each step, upload `…_A.jpg` as **01 / First panel** and `…_B.jpg` as **02 / Second panel**,
   then click **Analyze transition**. Each takes about 2 s. Open **Know more** to show all six
   definitions.
5. Optional: show the input-validation messages. Upload a non-image (e.g. a `.gif` or `.txt`); click
   Analyze with one panel missing; stop the backend and click Analyze ("Could not reach the
   analysis server").
6. Close with the honest headline numbers from `README.md`. On 136 held-out pairs from 31 books:
   macro-F1 over action/subject/scene is 0.394 against 0.174 for the majority class. Accuracy is 0.375,
   not significantly above always guessing action-to-action (0.353).

The web app always uses the **deployed** model. To demonstrate held-out behaviour live, use the CLI:
`.venv/bin/python predict.py demo/06_1943_3_3__3_4_A.jpg demo/06_1943_3_3__3_4_B.jpg --head models/head_dev.joblib`

## Exact source paths

The panels come from the COMICS dataset (US Golden Age comics, originally English), extracted under
`$CPT_WORKSPACE/data/comics/panels_dl/raw_panel_images/`
(default `/home/anonhp/Hard-Drive/comic-transition-workspace/…`):

| Step | Panel A | Panel B |
|---|---|---|
| 1 | `1094/35_0.jpg` | `1094/35_1.jpg` |
| 2 | `2438/26_2.jpg` | `2438/26_3.jpg` |
| 3 | `262/6_4.jpg` | `262/6_5.jpg` |
| 4 | `1094/24_1.jpg` | `1094/24_2.jpg` |
| 5 | `2206/63_6.jpg` | `2206/63_7.jpg` |
| 6 | `1943/3_3.jpg` | `1943/3_4.jpg` |
| 7 | `3637/31_2.jpg` | `3637/31_3.jpg` |
| 8 | `282/7_7.jpg` | `282/8_0.jpg` |

The images are not committed to Git (`demo/` is ignored), in line with the project rule that comic
images stay out of the repository.
