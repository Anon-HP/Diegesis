export const TRANSITION_TYPES = [
  {
    name: 'Moment-to-Moment  —  1%',
    description:
      'A very small change in time, showing nearly the same moment from a slightly different instant.',
  },
  {
    name: 'Action-to-Action  —  91%',
    description: 'The same subject is shown performing different stages of an action.',
  },
  {
    name: 'Subject-to-Subject  —  3%',
    description:
      'The scene remains connected while the focus shifts between different subjects or elements.',
  },
  {
    name: 'Scene-to-Scene  —  2%',
    description: 'The transition moves to a different time, place, or setting.',
  },
  {
    name: 'Aspect-to-Aspect  —  3%',
    description:
      'Different aspects of the same scene, mood, or environment are shown rather than a continuous action.',
  },
  {
    name: 'Non-Sequitur  —  0%',
    description:
      'The two images appear to have little or no logical relationship in time, action, subject, or setting.',
  },
] as const

export type TransitionTypeName = (typeof TRANSITION_TYPES)[number]['name']

export function getTransitionDescription(name: TransitionTypeName): string {
  return TRANSITION_TYPES.find((type) => type.name === name)?.description ?? ''
}
