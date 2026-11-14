## Goal: Automated Sprite Sheet Object Identification and Boundary Detection

I want a system that can analyze arbitrary pixel-art sprite sheets and identify, distinguish, and label the individual visual assets contained within them.

The system should work across different sprite sheet layouts, including regular tile grids, irregularly arranged collections of objects, densely packed assets, and sheets containing a mixture of terrain, structures, decorations, characters, and other graphical elements.

**The primary goal is to identify complete, logically distinct visual assets rather than simply divide an image into uniform tiles or isolated pixel regions.**

For each identified asset, the system should:

1. **Identify the asset:** Determine what the visual element represents and assign a descriptive label.
2. **Determine its boundaries:** Identify its precise location and pixel dimensions within the original image, including its bounding rectangle.
3. **Preserve logical grouping:** Recognize when multiple visual parts belong to one complete asset, even when those parts are visually separated or span multiple tiles.
4. **Distinguish adjacent assets:** Identify separate objects even when they are closely packed, touching, or visually similar.
5. **Handle variable dimensions:** Support assets of different widths, heights, and shapes without assuming every object occupies a fixed grid cell.
6. **Respect optional size constraints:** Allow a minimum pixel unit, such as 16×16, to be specified as contextual information without forcing all detected assets to have those dimensions.
7. **Represent pixel-level boundaries:** Where possible, distinguish the pixels belonging to an asset from surrounding background pixels or neighboring assets.
8. **Handle ambiguity:** Indicate when an asset's identity or boundaries are uncertain rather than presenting an arbitrary division as definitive.

### Expected output

A structured inventory of the assets detected in the image, containing:

- A unique identifier for each asset.
- A descriptive name or semantic label.
- Its pixel coordinates within the original sprite sheet.
- Its bounding rectangle (X, Y, width, height).
- Its precise pixel region or shape, where identifiable.
- Optional categorization and relationships to other assets.
- An indication of uncertainty where relevant.

### Intended outcome

Given a sprite sheet, the system should produce a spatially accurate, semantically meaningful map of its contents, enabling individual assets to be located, distinguished, referenced, and extracted without manually defining every object boundary.

The system should be general-purpose and should not depend on conventions specific to RPG Maker, any particular game engine, or a predetermined sprite sheet layout.
