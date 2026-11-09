/**
 * Scott McCloud's six panel-to-panel transitions (Understanding Comics, 1993) — the only labels the
 * backend model can return. `label` is the backend's canonical id; definitions follow PROJECT_REFERENCE.md.
 */
export const TRANSITION_TYPES = [
  {
    label: 'moment-to-moment',
    name: 'Moment-to-Moment',
    description:
      'A very small passage of time; the same subject or situation is shown across nearly immediate moments.',
  },
  {
    label: 'action-to-action',
    name: 'Action-to-Action',
    description: 'The same subject progresses through connected actions or stages of an action.',
  },
  {
    label: 'subject-to-subject',
    name: 'Subject-to-Subject',
    description:
      'The focus shifts between different subjects or elements within the same scene or continuing situation.',
  },
  {
    label: 'scene-to-scene',
    name: 'Scene-to-Scene',
    description: 'The transition crosses a meaningful change in time, place, or both.',
  },
  {
    label: 'aspect-to-aspect',
    name: 'Aspect-to-Aspect',
    description:
      'Different aspects or details of the same place, mood, atmosphere, or idea, without ordinary event progression.',
  },
  {
    label: 'non-sequitur',
    name: 'Non-Sequitur',
    description: 'The panels have no discernible logical or narrative connection.',
  },
] as const

export type TransitionLabel = (typeof TRANSITION_TYPES)[number]['label']
export type TransitionTypeName = (typeof TRANSITION_TYPES)[number]['name']

export function findTransition(label: string) {
  return TRANSITION_TYPES.find((type) => type.label === label)
}
