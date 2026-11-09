# Annotation Guidelines: McCloud Panel Transitions (six classes)

These rules are used for **every** label in this project, whether a human or a model assigns it.
The label set is fixed. These are the only valid labels, with these exact identifiers:

| id | label (canonical string) | McCloud name |
|----|--------------------------|--------------|
| 0 | `moment-to-moment` | Moment-to-moment |
| 1 | `action-to-action` | Action-to-action |
| 2 | `subject-to-subject` | Subject-to-subject |
| 3 | `scene-to-scene` | Scene-to-scene |
| 4 | `aspect-to-aspect` | Aspect-to-aspect |
| 5 | `non-sequitur` | Non-sequitur |

Do not use any other label. Iyyer et al.'s "continued conversation" is **not** a label here.
Conversation pairs must be given one of the six labels by the rules below. Usually that is
subject-to-subject (the focus moves between speakers) or moment-to-moment (the same speaker,
almost no time passes).

## What the annotator sees

You see Panel A (earlier) and Panel B (immediately after it), and nothing else. Do not guess
from context outside the two panels. Read any text in the panels (captions, balloons, sound
effects): it is part of the evidence.

## Definitions and decision rules

Work through these questions **in order** and stop at the first rule that clearly applies.

### Step 0: Is the pair usable?
Mark `valid = 0` (excluded, no label) if either image is not a story panel (an advertisement,
cover, text-only page, publisher indicia, or a fragment from a bad crop), or if the two images
are obviously not consecutive panels of the same story. Excluded pairs are kept in the files
with `valid=0` and are never used for training or evaluation.

### Step 1: Non-sequitur
Choose **non-sequitur** only if you can find **no** logical or narrative link between A and B:
no shared character, place, object, theme or text thread, and no caption that explains the jump.
A jump to a new place, or the start of a new story, is **not** a non-sequitur when a caption or
the story structure explains it. That is scene-to-scene. Real non-sequiturs are extremely rare
in narrative comics.

### Step 2: Scene-to-scene
Choose **scene-to-scene** when the transition crosses a **significant** gap in time and/or space
that the reader must bridge with deductive reasoning. Signals:
- Captions like "LATER", "MEANWHILE", "THAT NIGHT", "NEXT DAY", "BACK AT …", "ELSEWHERE", "MILES AWAY".
- A clearly different location (a city street, then the inside of a ship) with no continuous movement linking them.
- A clearly different set of characters in a different setting, as when the story cuts away.

A character simply walking into the next room in continuous action is **not** scene-to-scene;
it is action-to-action. If the location is the same but a caption announces a large time skip
("Hours later…"), choose scene-to-scene.

### Step 3: Aspect-to-aspect
Choose **aspect-to-aspect** when time essentially does **not** advance and the "eye wanders"
over different aspects of **one place, mood, idea or atmosphere**. The panels establish
atmosphere or setting (details of a room, the landscape, the rain, the crowd) **rather than**
advancing an event or following a particular actor's action or speech.

**Aspect-to-aspect vs subject-to-subject.** This is the hardest boundary.
- If B shifts to a **different participant in an ongoing event or exchange** (another speaker,
  someone reacting, the opponent in a fight, the target of an action), and the story is moving
  forward, the label is **subject-to-subject**.
- If A and B show different **details or facets of a setting or mood**, with no story
  progression and no actor-driven exchange between them, the label is **aspect-to-aspect**.
- Test: "Could the order of A and B be swapped with no loss of narrative sense, and is the purpose
  to set a mood or place?" If yes to both, use aspect-to-aspect. If B *responds to* or *follows from*
  A within the scene, use subject-to-subject.

### Step 4: Same subject, or a new subject?
Find the main subject (character or object) that each panel centres on.

- **Subject-to-subject**: B centres on a **different** subject (a character, group or object)
  than A, **within the same scene**. Examples: speaker A, then listener B replying. A villain
  aiming, then a cut to the hero. A hero, then a close-up of a bomb in the same room. The time
  gap is small to moderate and the scene and idea continue.
- If the main subject is the **same** in A and B, go to Step 5.

When a panel contains several characters, the subject is whoever is the focus: in the
foreground, acting or speaking. If the focus changes from one character to another, use
subject-to-subject. If the same group is shown performing a continued action, treat it as the
same subject.

### Step 5: Same subject. Moment-to-moment or action-to-action?
- **Action-to-action**: the same subject goes through a **distinct, meaningful progression** of
  action. One action, or stage of an action, is completed or replaced by the next: winding up and
  then hitting, running and then jumping, a car speeding and then crashing, a character standing
  and then sitting down to write. This is the most common class in Western comics.
- **Moment-to-moment**: the same subject in **nearly the same** situation, with only a tiny
  change: a blink, a slight turn of the head, a drop falling a little further, an expression
  changing. A and B could almost be consecutive film frames. In dialogue: the **same** speaker,
  the **same** pose and framing, continuing to talk with no meaningful action between panels.

Tie-breaker: if you hesitate between these two, ask whether something *happened* (a completed
or new action, a visible state change). If yes, use action-to-action. If the change is barely
perceptible, use moment-to-moment.

## Ambiguity handling

- Always give **one** label and a confidence: `high`, `medium` or `low`.
- Optionally record a `second_choice` label, which must also be one of the six. This is
  metadata only and is never used as a training target.
- Use `low` confidence rather than leaving a pair unlabeled, unless the pair is invalid (Step 0).
- Write a one-line rationale naming the decisive evidence ("caption LATER", "same man, punch
  lands", "cut from speaker to listener").

## Quality control

- Inter-annotator agreement is measured on a doubly-annotated subset (Cohen's kappa).
  Iyyer et al. report κ = 0.605 for a related five-class scheme, so disagreement is expected.
- Label provenance is always recorded:
  - `human`: assigned or verified by a person following these rules.
  - `llm`: assigned by a large vision-language model (Claude) following these rules. These are
    **machine-generated labels**, not human ground truth.
  - `synthetic`: a pair built automatically, such as two panels from unrelated books presented
    as a non-sequitur. This is weak supervision only and is never part of the main evaluation.
- Machine labels must never be reported as human-verified.
