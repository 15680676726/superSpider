# Public Legacy Site Docs

This directory stores old website markdown that no longer represents the canonical public documentation surface.

Why these files were moved:

- the public website is now driven by `website/src/pages/Docs.tsx`
- the old markdown set still contained stale `Spider Mesh`, `CoPaw`, and retired-product wording
- leaving those files under `website/public/` caused obsolete content to stay publicly reachable even after the visible site shell was updated

Rules:

- do not restore these files to `website/public/`
- if a topic is still part of the current public product story, rewrite it into the active website docs surface instead of reviving the legacy markdown
- if a file matters only for history, keep it archived here
