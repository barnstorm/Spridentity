# Limits

## Boundaries

- Different objects drawn touching at full width, with nothing in the pixels to tell them
  apart, are reported as one flagged asset.
- An object with a narrow waist exactly on a unit line is cut there. On the furniture
  example the round table top is separated from its pedestal this way, and neither part is
  flagged.
- Some joins and cuts are wrong without being flagged. On the furniture example a desk and
  a bookshelf are one asset, and one cabinet is two.
- Lattices are assumed to start at pixel 0 with no gutters. Sheets with gutters work
  through background separation instead.
- On edge-to-edge tiles, which tiles form one terrain set is a judgement call.

## Unit

- Unit inference is unreliable. On 173 sheets with a known tile size it was right on 65,
  wrong on 37 and declined to guess on 71. Pass `--unit` when you know it.
- The unit check can refute a unit that is too small or shifted, but not one that is a
  multiple of the true size.

## Names

- Names from local models are often wrong, and the models say "high confidence" whether
  right or wrong. See [Naming evaluation](Naming-Evaluation) for measured rates.
- CLIP hints can only suggest words that are in the vocabulary.
- A sprite that is a fragment, or several things merged, cannot be named correctly by any
  method; fix the boundary first.
- The numbers in the evaluation come from three sheets and one judge. Treat them as
  indications. [Judging with another model](Judging-With-Another-Model) explains how to
  check them independently.
