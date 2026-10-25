# DevServer Architecture

**Part 14: Testing**

---


### The suites

Four suites, each run from its own directory; none of them needs a model or a
running service.

| Suite | Where | Run |
|-------|-------|-----|
| DevServer | `devserver/tests/` (pytest; `devserver/pytest.ini` keeps `testfiles/` out of the collection) | `cd devserver && pytest` |
| GPU service | `gpu_service/tests/` (pytest) | `cd gpu_service && pytest tests` |
| Frontend units | `public/ai4artsed-frontend/src/**/__tests__/*.spec.ts` (vitest, jsdom) | `cd public/ai4artsed-frontend && npm run test:unit` |
| Frontend types | the whole `src/` under `vue-tsc` | `cd public/ai4artsed-frontend && npm run type-check` |

The pre-commit hook (`scripts/git-hooks/pre-commit`, installed by
`scripts/install-hooks.sh`) runs the policy tests of `devserver/tests/`: with
`--staged` against the index the model literals, the element structures, the
GPU admission coverage, the three i18n gates (label grammar, direct address,
filler phrases) and the public surface; under pytest on a `checkout-index`
copy of the index the config references, the output-config carry list and the
canvas presets. Each of them also runs under pytest with the DevServer suite.

`devserver/testfiles/` holds replay and probe scripts that talk to running
services (ComfyUI, the GPU service, the DevServer) and exit at import time
when their inputs are missing; they are run by hand, never collected.

### Running Tests

```bash
cd devserver && pytest                                   # DevServer
cd gpu_service && pytest tests                           # GPU service
cd public/ai4artsed-frontend && npm run test:unit        # frontend units
cd public/ai4artsed-frontend && npm run type-check       # frontend types
```

---
