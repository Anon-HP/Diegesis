# Data Sources

Checked on 2026-11-01. The facts below come from fetching the hosts and range-reading the archives
directly, not from the dataset papers.

## Used: COMICS (Iyyer et al., CVPR 2017)

- **Content:** US Golden Age comics (1938–1954) taken from the Digital Comic Museum. They were
  originally published in English, which meets the project's language requirement.
- **Host (live, no registration):** `https://obj.umiacs.umd.edu/comics/`. The old `umiacs.umd.edu/~miyyer`
  path returns 404.
- **Files actually used:**
  - `raw_panel_images.tar.gz` (65.67 GB in full). The panels are already cropped and stored as
    `raw_panel_images/<book>/<page>_<panel>.jpg`. We downloaded **only the first 3.5 GB** of the
    compressed archive, using the resumable, verified `scripts/fetch_comics_part.sh`, and extracted it
    with `tar -xzf … --skip-old-files`. The result is **204 complete books**. Book folders appear in the
    archive in no particular order. The last folder (book 1450) is truncated and is excluded with
    `--partial-book 1450`.
  - `predadpages.txt`: pages the COMICS authors predicted to be advertisements. These pages are excluded.
  - `COMICS_ocr_file.csv` (255 MB): the authors' OCR, made with Google Vision. It is used **only**
    as candidate metadata when choosing which pairs to annotate (for example, finding captions such
    as "LATER" to enrich the scene-to-scene class). It was also used as a reference text for two
    diagnostics: tuning Tesseract's settings by word recall, and estimating how often a caption cue is
    recoverable. It is **never** an input at inference and never a model feature. At inference, the
    model runs its own OCR (Tesseract) on the two input images.
- **Reading order:** sort by the integers (page, panel). The order of panels within a page comes
  from the COMICS pipeline and has not been independently verified. Annotators mark broken pairs
  as invalid.
- **Transition labels:** **none released.** The 250 pairs Iyyer et al. annotated are not in the bucket
  or in the GitHub repo (`miyyer/comics`, which holds code only under the MIT licence). Those labels
  also used a different five-category scheme, so they could not be used even if available.
- **Licence:** the data has no explicit licence statement. The underlying books are offered as
  public domain (in the US) by the Digital Comic Museum. We use the data for research only and
  do **not** redistribute any images in this repository. Images stay in the external workspace
  directory, outside version control.

## Evaluated but not used

| Source | Status | Why not used |
|---|---|---|
| DCM772 (gitlab.univ-lr.fr/crigau02/dcm-dataset) | Live | Ground-truth boxes only, with no images. Images must be downloaded from Digital Comic Museum, which sits behind a Cloudflare challenge and needs an account, or requested from the authors. Panel boxes are unordered and there are no transition labels. |
| Comics100 / CoMix (github.com/emanuelevivoli/CoMix) | Live | Annotations only. Images have to come from the 129 GB COMICS page archive or from DCM. No transition labels. |
| CoMix v0.1 pages on Hugging Face | Live, gated (auto-accept) | Full pages, not panels. Panel boxes come from a detector and are not in reading order, so we would have to build our own panel segmentation and reading-order step, which is out of scope. Kept as a possible future source (CC-BY-SA-4.0). |
| VLR-CVC/ComicsPAP | Live | 165 GB, and it is built for a different task. |
| Manga109, the manga McCloud dataset (arXiv 2312.08720) | — | Excluded: not originally English. |
| eBDtheque | Unreachable / registration | Mostly French. Excluded. |

No public dataset of Western, originally-English comics labelled with McCloud's six transitions
was found. Every transition label in this project was therefore created here. See
`annotation_guidelines.md` and `data/manifest.csv`, where every row records its label provenance.
