# 0004 — GPU texture compression lives in mabda; sankoch stays lossless and supplies primitives

- **Status**: Accepted
- **Date**: 2026-10-13
- **Deciders**: the user (sankoch / mabda maintainer)

## Context

sankoch's roadmap carried "2.8.6 — GPU texture compression (BC1–BC7 / ASTC)" and said its first step
was a home decision, not code: sankoch is the home of every *lossless* codec, but block texture
formats are lossy and GPU-specific, and mabda (the GPU library) already had their format enums.

What was true on 2026-10-13:

- mabda owns the `MABDA_TEXFMT_BC*` / `ASTC_*` ids, the VkFormat / DXGI mappings
  (`src/asset_format.cyr`), the DDS and KTX2 loaders (`src/asset_load.cyr`), per-backend compression
  capability masks, and compute dispatch (`src/compute.cyr`).
- mabda's `[deps] stdlib` already lists `sankoch` (through chitra), and the stdlib's `lib/sankoch.cyr`
  is sankoch's full bundle.
- mabda's KTX2 loader rejects every supercompressed file ("needs a decompressor mabda does not have"),
  and two of KTX2's three supercompression schemes, Zstandard and ZLIB, are sankoch codecs.

## Decision

**GPU texture compression is mabda's work. sankoch keeps to lossless codecs and provides the
lossless primitives a texture pipeline leans on.**

- **In scope (sankoch)**:
  - 2.8.6 leaves sankoch's ladder; the next sankoch release is the 2.8.x-closeout P(-1) pass.
  - The primitives that exist today and need no sankoch change: `zstd_decompress` /
    `zlib_decompress_capped` for KTX2 supercompression schemes 2 / 3 on load, and
    `zstd_compress_level` / `zlib_compress` on write.
  - Primitives on request: if mabda's encoder wants rate-distortion optimization, a public "bits this
    block costs after LZ + entropy coding" estimate built from sankoch's match finders and coders. It
    is scheduled when mabda files the shape it needs.
- **Out of scope (sankoch)**: any lossy codec; BasisLZ / ETC1S transcoding (KTX2 scheme 1), which is
  a texture transcoder rather than a general lossless codec.
- **Filed for mabda**: `mabda/docs/development/issues/2026-10-13-gpu-texture-compression-encoder.md`
  plus a backlog line in mabda's roadmap, for a later date.

## Consequences

- **Positive**
  - sankoch's identity stays "every lossless codec", with no qualifying needed in `CLAUDE.md`.
  - The encoder will sit next to the format ids, the loaders, the capability masks and the GPU
    sampling path that validate it.
  - mabda can open KTX2 Zstandard / ZLIB support with code it already links.
- **Negative**
  - A texture encoder that wants RDO depends on a sankoch API that does not exist yet, so the two
    repos have to agree its shape first.
- **Neutral**
  - The 2.8.x ladder loses a feature release: after 2.8.5 comes the closeout pass.

## Alternatives considered

- **In sankoch, as the roadmap first framed it** ("modular by profile" would have kept it out of
  every consumer that doesn't want it). Lost: the codec is lossy, and its validation, formats and
  consumers are all GPU-side. sankoch would have needed mabda's format knowledge, or a duplicate of it.
- **A new repo for texture codecs.** Lost: mabda already is the GPU home. A third repo would add a
  dependency edge and duplicate the format enums.

## References

- sankoch roadmap: *Backlog*, "Primitives for mabda's texture work".
- mabda: `src/asset_load.cyr` (`_ktx2_parse`'s supercompression gate), `src/asset_format.cyr`.
- Khronos KTX 2.0 specification (`supercompressionScheme`).
