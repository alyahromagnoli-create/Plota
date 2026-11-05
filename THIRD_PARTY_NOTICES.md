# Third party notices

## v7 additions

SCI Figure Gallery (https://github.com/Chutj/sci-figure-gallery), commit 0ae742f565338a2665430e6fe352b6c79fbbb2f5: MIT code/documentation, Copyright (c) 2026 Chutj. The palette sampling strategy was adapted from assets/js/gallery-tools.js. Project notice is retained in assets/gallery/SCI_Gallery_LICENSE.txt. The application carries palette values, references and design notes; paper images are not bundled. Original figures have their own individual licenses, recorded in catalog metadata. Sampled colors are approximate, not verified author-specified rendering parameters.

Seaborn (https://seaborn.pydata.org): six original categorical palettes, BSD-3-Clause notice retained in assets/gallery/seaborn_LICENSE.md. Common statistical plot forms are rendered using Matplotlib and NumPy; no Seaborn installation is required by exported scripts.

Scientific colour maps by Fabio Crameri and cmcrameri contributors (https://www.fabiocrameri.ch/colourmaps/, https://github.com/callumrollo/cmcrameri): 22 sampled colormap lookup tables, MIT notice retained in assets/gallery/cmcrameri_LICENSE.txt. Original library version is recorded in assets/gallery/palettes.json.

Additional input libraries: xlrd, odfpy, PyArrow and h5py. Collected upstream license notices are in licenses/ and bundled into the single-file application. These readers are not needed by exported plot.py, which operates on its adjacent CSV snapshots.

Plota uses third-party libraries and runtime components. Their own licenses apply independently to those components. Publishing this repository does not replace those licenses or grant a new license over third-party works.

## SciencePlots

- Project: https://github.com/garrettj403/SciencePlots
- Copyright (c) 2018 John Garrett
- License: MIT, retained verbatim in [assets/scienceplots/LICENSE](assets/scienceplots/LICENSE).
- Upstream snapshot: b9b16959570bd2fbc9ff5118bacc423c3bddd592.
- Original science, ieee, nature, bright and no-latex style files and SHA256 provenance are retained in assets/scienceplots. Parsed settings and the full notice are embedded in engine.py and exported plot.py. Every export also includes SciencePlots_LICENSE.txt.
- Adaptations: no external TeX, exact user-defined figure dimensions without tight cropping, user-controlled font size and DPI, local font fallback, and explicit per-layer color/line cycles.

## Python packages and native runtimes

Runtime components include CPython, Tcl/Tk, tkinterdnd2/tkdnd, NumPy, pandas, Matplotlib and its font/rendering dependencies, openpyxl, Pillow and their dependencies. PyInstaller packages the standalone executable. Applicable package license files collected from the build environment are included in the release license archive; consult those upstream notices for the component-specific terms.

Tavotto is an optional external editor: https://github.com/Tavotto/Tavotto. Its source was used separately to verify exported figure compatibility. Tavotto source and engine are not included in the Plota application or repository.

The icon geometry and application interface are part of Plota. Public example datasets are synthetic and do not contain research measurements. No blanket open-source license for Plota's own code is specified in this release.
