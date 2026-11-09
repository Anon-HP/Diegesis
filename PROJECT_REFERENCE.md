# English-Language Comic Panel Transition Classification

## Project scope

Build a machine-learning model that receives exactly two images of consecutive, correctly ordered panels from the same English-language comic and predicts the narrative transition between them.

The task is panel-pair transition classification. It is not page segmentation, panel detection, reading-order discovery, comic generation, dialogue transcription, character identification, or general story summarization. The inference interface must accept two panel images directly.

Only English-language comics are in scope. Do not include translated editions of comics originally created in another language, or datasets and methods whose comic content is in another language. The target domain is English-language Western comics.

## One fixed label taxonomy: Scott McCloud's six transitions

Use McCloud's six panel-to-panel transition categories as the sole target-label schema throughout data preparation, training, validation, evaluation, and inference:

1. **Moment-to-moment**: A very small passage of time; the same subject or situation is shown across nearly immediate moments.
2. **Action-to-action**: The same subject progresses through connected actions or stages of an action.
3. **Subject-to-subject**: The focus shifts between different subjects or elements within the same scene or continuing situation.
4. **Scene-to-scene**: The transition crosses a meaningful change in time, place, or both.
5. **Aspect-to-aspect**: The panels present different aspects or details of the same place, mood, atmosphere, or idea, without ordinary event progression being the main focus.
6. **Non-sequitur**: The panels have no discernible logical or narrative connection.

The classifier must always use these six names and meanings. Do not silently substitute another paper's categories, merge categories, rename classes, or add a seventh class.

## Important distinction from Iyyer et al. (2017)

Iyyer et al., *The Amazing Mysteries of the Gutter: Drawing Inferences Between Panels in Comic Book Narratives* (CVPR 2017), analyzed 250 randomly selected consecutive panel pairs from the COMICS dataset. Their inter-panel annotation scheme used five categories:

- Moment-to-moment
- Action-to-action
- Subject-to-subject
- Scene-to-scene
- Continued conversation

This is not the same as McCloud's six-category taxonomy. In particular, Iyyer et al.'s “continued conversation” is not a direct one-to-one replacement for either “aspect-to-aspect” or “non-sequitur.” Do not train a six-class model by simply renaming or mechanically mapping the five Iyyer categories. Their labels may be used as weak guidance or candidate metadata, but any pair used as a McCloud-labelled training example must be assigned under the fixed six-class annotation rules. Re-annotate, adjudicate, or exclude cases that cannot be mapped reliably.

The Iyyer et al. paper reports that the annotators agreed on 68% of inter-panel transition annotations (Cohen's κ = 0.605). This is evidence that the task has genuine annotation ambiguity. It must be handled explicitly through clear decision rules, quality checks, and careful evaluation, not ignored.

## Relevant English-language data sources described in the literature review

### COMICS

- US Golden Age superhero/adventure comics, 1938–1954, sourced from the Digital Comics Museum.
- Approximately 3,948 books, 198,657 pages, and 1.23 million panels, according to the literature review.
- Panel and textbox information is available, but annotation quality is uneven: the review reports human ground truth for only 500 pages and 1,500 textboxes, with much of the larger-scale extraction automatically generated.
- Iyyer et al. used 250 consecutive panel pairs for their five-category inter-panel analysis.
- This is the most directly relevant starting point in the reviewed literature because it is a large English-language comic corpus with panel sequences and a published study of consecutive-panel transitions.
- The availability of the exact 250 pair annotations, their images, and their reuse terms must be checked in the actual dataset/repository before relying on them.

### DCM772

- 772 pages from 27 Golden Age comic books, using the same broad source collection as COMICS.
- The review reports 4,470 panels, 10,757 characters, and 5,438 faces, with comparatively precise bounding-box annotations.
- It does not provide transition labels or dialogue annotations in the reviewed description.
- It may be useful as an additional source of panel images or ordered pairs if the released files preserve page and reading-order information. That suitability must be verified before use.

### Comics100 / Comics Datasets Framework

- Approximately 5,422 pages from 100 curated American-style comic books.
- The review reports panel, character, text, and face bounding boxes in a standardized annotation format.
- Its labels were partly bootstrapped from an existing detector, so their quality should not automatically be treated as independently verified ground truth.
- It may provide additional English-language panel images or ordered pairs if the released annotations and source files support that use. It does not, in the reviewed description, supply McCloud six-class transition labels.

### Data caveats

The reviewed datasets do not establish the existence of a large, ready-to-train dataset labelled with McCloud's six transition types. Do not imply that they do. The implementation must verify what data and annotations are genuinely downloadable, what their licenses permit, and whether consecutive-panel order can be recovered. Do not fabricate labels, annotation counts, dataset access, or model performance.

## Relevant research findings

- Iyyer et al. show that understanding the transition between consecutive panels can require combining visual content and comic text; image-only and text-only information may each be insufficient for narrative understanding.
- Their work operationalizes closure and studies inter-panel transition types, but its five-category scheme differs from the six categories required here.
- The literature review identifies McCloud's six-category taxonomy as a plausible ML label set that had not, in the review's account, been used as a direct classification target.
- The review emphasizes that narrative understanding is less mature than panel detection and OCR. Detecting what appears in a panel is not equivalent to understanding how two panels relate.
- Dataset quality and label consistency are central constraints. Results from different papers may not be directly comparable when their labels, splits, and metrics differ.

## Required model behavior

**Input:** Two images, Panel A followed by Panel B, depicting consecutive panels from the same English-language comic.

**Output:** Exactly one of the six McCloud labels listed above. A confidence score may accompany the label, but confidence is not an additional class. The inference system must not output labels from another taxonomy.

The model may use any suitable internal representation or processing pipeline. For example, it may use a visual encoder, OCR/text features extracted from the panel images, paired-image interaction, or a multimodal architecture. These are implementation choices, not additional user-facing inputs. The externally visible task remains classification from the two supplied panel images.

## Source references

- Iyyer, M., Manjunatha, V., Guha, A., Vyas, Y., Boyd-Graber, J., Daumé III, H., & Davis, L. (2017). *The Amazing Mysteries of the Gutter: Drawing Inferences Between Panels in Comic Book Narratives*. CVPR 2017. https://openaccess.thecvf.com/content_cvpr_2017/html/Iyyer_The_Amazing_Mysteries_CVPR_2017_paper.html
- McCloud, S. (1993). *Understanding Comics: The Invisible Art*. Tundra Publishing / HarperPerennial.
- The source literature review supplied with this project, *Machine Learning for Comic Book Analysis: A Research Literature Review* (compiled August 2026), especially its discussion of COMICS, Western comics datasets, closure, and McCloud's six transition categories.
