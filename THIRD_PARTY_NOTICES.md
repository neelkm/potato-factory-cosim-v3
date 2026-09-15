# Third-party components

New project code is provided under Apache-2.0. Existing third-party notices remain in their source files and asset archives.

- NVIDIA cosim is retrieved at the exact commit in `vendor/nvidia_cosim_revision.json`. Its unchanged source is used locally and is not republished as part of this project's Git source. Obtain it through your existing access to the original repository.
- ovnewton and ovfmi source are fetched from their original repositories at pinned commits. Their Apache-2.0 notices and package terms remain applicable. Native ovstage, ovphysx and ovrtx packages retain their original distribution terms.
- PhysX headers and native bridge interfaces retain the notices in the header snapshot. The small FMI header and wrapper include NVIDIA Apache-2.0 attribution.
- Newton, Warp, OpenUSD, NumPy, SciPy, FMPy, Pillow, ImageIO and the other Python packages retain their own package licenses. Their exact installed versions are recorded in the dependency locks.
- Blender is obtained from its official distribution; its license remains applicable. The editable factory scene is a separate project artifact.
- The Franka and SimReady forklift assets retain their original NVIDIA asset notices and terms. Poly Haven lighting and floor textures are CC0. See `docs/asset_provenance.md` for credits and source records.

No third-party account credentials, workstation authentication files or personal access tokens belong in the repository or release bundles.
