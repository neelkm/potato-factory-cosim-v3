# Asset provenance

The factory, truck, potatoes, robot, cartons and forklift were modeled procedurally in Blender for this project. Photographs guided proportions, finish and equipment details; they were not used as geometry or composited into the video.

## Photographic references

- Wyma Solutions, [Wet Hopper](https://www.wymasolutions.com/products/hoppers/wet-hopper). Reviewed photo: https://www.wymasolutions.com/hubfs/WymaSolutions_April2021/images/002-B-Wet-Hopper-3.jpg. Local research copy: `reference/v2/wet_hopper.jpg`. Used for wet produce handling, stainless equipment and potato appearance. Photo copyright remains with its owner.
- Bulk Lines, [bulk transport reference](https://www.bulklines.co.nz/). Reviewed photo: https://static.wixstatic.com/media/27e8b6_18766986542e4c78befb678e68380556~mv2.jpg. Local research copy: `reference/v2/bulk_tipper.jpg`. Used for tipper proportions, body ribs and truck details. Photo copyright remains with its owner.
- [KRONEN potato processing line](https://www.kronen.eu/en/solutions/processing-line-for-potatoes-up-to-1200-kg-h), equipment layout reference.

## Licensed render assets

- [Hangar Interior HDRI](https://polyhaven.com/a/hangar_interior), Poly Haven, CC0. Authors: Dimitrios Savva and Jarod Guest. File: `output_v2/hangar_interior_4k.hdr`. Used for photographic environmental illumination and reflections. Download metadata: `reference/v2/hdri_files.json`.
- [Concrete Floor 02](https://polyhaven.com/a/concrete_floor_02), Poly Haven, CC0. Author: Rob Tuytel. Files: `output_v2/concrete_floor_02_diff_2k.jpg`, `concrete_floor_02_rough_2k.jpg`, and `concrete_floor_02_nor_gl_2k.jpg`. Download metadata: `reference/v2/concrete_files.json`. Used as the warehouse floor's color, roughness and normal maps.

## Generated potato skin

Tool: OpenAI image generation, new texture generation without supplied reference images. The generated texture is used as base color on the smaller, irregular potato meshes; visible defects are authored mesh material regions.

Project asset: `output_v2/potato_albedo.png`.

Original generated file: `C:/Users/neelakantanm/.codex/generated_images/01a090e3-65ef-7273-af73-ce04d41d1d6d/exec-f823d939-f44e-4d80-a4b4-17aa7c18530b.png`.

Exact prompt:

> Create a single square seamless tileable photorealistic potato-skin BASE COLOR texture for a physically based 3D factory simulation. A flat orthographic macro scan of natural washed russet potato skin, covering the entire image edge to edge. Muted light earthy tan, warm beige and subtle ochre, with tiny irregular pores, fine reticulated cork-like skin, faint freckles and a few shallow small potato eyes. Natural low contrast, no shiny coating. Uniform diffuse illumination with absolutely no directional highlights, cast shadows, gradient, vignette or depth of field. Fine realistic grain; avoid exaggerated cracks, rock, bread, fried food, big blotches or cartoon texture. No whole potatoes, no potato silhouette, no background, no text, no borders. 2048 by 2048 pixels if possible. This image will be wrapped around small irregular potato meshes; tile edges should match in both directions.

The water surface is reconstructed from recorded PhysX particle positions. It is not generated footage. Camera motion, labels and the tracking marker are presentation elements; the product and load movements come from the recorded physics simulation.
