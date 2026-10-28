# Anatomical model attribution

The 3D body shown in the demonstration interface is not original work for this thesis.
It uses anatomical models from **BodyParts3D**, published by the Database Center for
Life Science (DBCLS), Japan.

## Source

- Dataset: [BodyParts3D 4.0](https://dbarchive.biosciencedbc.jp/en/bodyparts3d/download.html)
- Copyright: BodyParts3D, © The Database Center for Life Science
- Author's license statement (updated 27 February 2025):
  [License to use this database](https://dbarchive.biosciencedbc.jp/en/bodyparts3d/lic.html)
- Dataset DOI: [10.18908/lsdba.nbdc00837-000](https://doi.org/10.18908/lsdba.nbdc00837-000)
- Reference: Mitsuhashi et al., *BodyParts3D: 3D structure database for anatomical
  concepts*, Nucleic Acids Research (2009), [doi:10.1093/nar/gkn613](https://doi.org/10.1093/nar/gkn613)

## Licences

Most structures in this view, including the organs, skeleton, muscles and vessels
other than the lung lobes, come from BodyParts3D 4.0 and are used under the
[Creative Commons Attribution 4.0 International licence (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
That licence allows reuse and adaptation if the copyright holder and the licence
are named. This notice is that attribution.

The five lung-lobe meshes (upper, middle and lower lobe of the right lung, and
upper and lower lobe of the left lung; BodyParts3D identifiers FMA7333, FMA7337,
FMA7383, FMA7370 and FMA7371) come from BodyParts3D 3.0, obtained through
[Kevin-Mattheus-Moerman's STL distribution](https://github.com/Kevin-Mattheus-Moerman/BodyParts3D).
Those lung meshes, and the geometry adapted from them, remain under the
[Creative Commons Attribution-ShareAlike 2.1 Japan licence (CC BY-SA 2.1 JP)](https://creativecommons.org/licenses/by-sa/2.1/jp/).
In this repository they appear as the `lungs` mesh in `organs.glb` and in the
sampled graph `organs-graph.json`.

Older BodyParts3D files sometimes name CC BY-SA 2.1 Japan in their headers.
The current statement from the database owner, linked above, is CC BY 4.0 for
BodyParts3D 4.0. The lung lobes keep the ShareAlike terms of the 3.0 distribution
they were taken from.

## What was changed here

The selected structures were simplified, converted to a single GLB file, sampled
into a surface graph, and drawn in one colour for the demonstration view. They
share one placement in the scene. The markers on the body point to a region
associated with a record. They are not a diagnosis, a lesion, or a scan of a
real person.

No endorsement by the Database Center for Life Science, the paper's authors, or
the distributor of the lung meshes is implied.
