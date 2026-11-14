# Limits

## Boundaries

- Different objects can touch along their full width. If the pixels do not show a
  difference, the tool reports them as one asset with a flag.
- If an object has a narrow part exactly on a unit line, the tool cuts the object there.
  On the furniture sheet, this divides the top of the round table from its pedestal. The
  two parts have no flag.
- Some incorrect joins and cuts have no flag. On the furniture sheet, a desk and a
  bookshelf are one asset, and one cabinet is two assets.
- The tool assumes that a lattice starts at pixel 0 and has no gutters. For sheets with
  gutters, the tool uses the background to divide the assets.
- On tiles that touch on all sides, it is not always clear which tiles make one terrain
  set.

## Unit

- The tool cannot calculate the unit reliably. On 173 sheets with a known tile size, the
  result was correct on 65 and incorrect on 37. On 71, the tool gave no result. Use
  `--unit` when you know the unit.
- The unit check can find a unit that is too small or not aligned. It cannot find a unit
  that is a multiple of the correct size.

## Names

- Names from local models are frequently incorrect. The models report high confidence for
  correct names and for incorrect names. [Naming evaluation](Naming-Evaluation) gives the
  measured rates.
- CLIP hints can only give words that are in the vocabulary.
- If a sprite is a fragment, or contains more than one object, no method can give it a
  correct name. Correct the boundary first.
- The numbers in the evaluation come from three sheets and one judge. Use them only as an
  indication. [Judging with another model](Judging-With-Another-Model) tells you how to do
  an independent check.
