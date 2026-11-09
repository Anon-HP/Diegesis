You are annotating comic panel transitions for a research dataset. Work carefully and independently.

1. Read the guidelines in full: /home/anonhp/Codes/English-Comics-Panel-Transition/docs/annotation_guidelines.md
2. Read the batch file {BATCH_CSV}. It has columns pair_id, composite. Each composite is a single JPEG with
   PANEL A (first, left) and PANEL B (the next panel, right) from a US Golden Age comic.
3. For EVERY row, in order, open the composite image with the Read tool and look at it. Read the lettering.
   Decide using ONLY what is visible in the two panels, following the guideline steps 0-5 in order.
   Do not look at any other files in the project (no other batches, no label files, no code).
4. Write your results to {OUT_CSV} (CSV with header) with columns exactly:
   pair_id,valid,label,confidence,second_choice,rationale,annotator
   - valid: 1, or 0 if the pair is unusable (ad/cover/fragment/not consecutive story panels) — then leave label empty.
   - label: exactly one of moment-to-moment, action-to-action, subject-to-subject, scene-to-scene, aspect-to-aspect, non-sequitur
   - confidence: high | medium | low
   - second_choice: one of the six labels or empty
   - rationale: <= 20 words, no commas inside (use ;)
   - annotator: {ANNOTATOR}
   Write the file incrementally (rewrite it after every ~10 pairs) so progress is never lost.
5. Do not use any label outside the six. Be honest about uncertainty with the confidence field.
   Don't default to one class: judge each pair on its own evidence.
6. When finished, reply with only: the number of rows written, and counts per label.
