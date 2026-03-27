# Spider Mesh Website

`website/` is the outward-facing site for the Spider Mesh system. It is used to:

- present what Spider Mesh is and how it works
- link users into the Runtime Center and core architecture docs
- keep `/docs/:slug` and `/release-notes` as stable public-facing entry points

The operational frontend is `console/` and the Runtime Center it serves.

## Install

```bash
npm install
```

## Development

```bash
npm run dev
```

Default local address: `http://localhost:5173`

## Build

```bash
npm run build
```

## Scope

- Keep the story centered on Spider Mesh as a local execution system.
- Use `console/` and Runtime Center as the main product surface for real operations.
- Historical markdown under `public/docs` and `public/release-notes` is retained only as version archive input.
