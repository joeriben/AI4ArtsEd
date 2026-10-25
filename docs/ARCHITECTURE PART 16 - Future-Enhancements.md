# DevServer Architecture

**Part 16: Future Enhancements**

> **Last Updated:** 2025-11-09
> **Current Release:** v2.0.0-alpha.1

---

## v2.0.0-alpha.1 Status (2025-11-09)

### ✅ Completed Features

- [x] 4-Stage orchestration fully operational
- [x] LivePipelineRecorder as single source of truth
- [x] MediaStorage completely removed
- [x] stage4_only feature for fast regeneration
- [x] media_type UnboundLocalError fixed
- [x] SpriteProgressAnimation for progress indication
- [x] Text transformation pipelines (dada, bauhaus, etc.)
- [x] Image generation (SD3.5 Large via ComfyUI)
- [x] Vector fusion workflow (CLIP+SD35)

### ⏸ Postponed Features

- [ ] **SSE Streaming** - Postponed
  - Implementation stashed
  - Can be reactivated later as enhancement
  - SpriteProgressAnimation sufficient for v2.0.0-alpha.1
  - See: DEVELOPMENT_DECISIONS.md (Active Decision 1)

---

## Future Enhancements

### Phase 1: Complete Output-Pipeline System
- [x] Implement `single_text_media_generation.json` pipeline
- [x] Implement `dual_text_media_generation.json` pipeline
- [x] Create standard output configs (sd35_large, vector_fusion)
- [x] Test text→media chains
- [ ] Additional output configs (flux1_dev, gpt5_image, etc.)

### Phase 2: Advanced Features
- [ ] **SSE Streaming** - Real-time progress updates
  - Status: Code stashed, ready to reactivate
  - Required: Frontend integration, backend routes restoration
- [ ] `image_text_media_generation` pipeline implementation
  - Status: NOT IMPLEMENTED (as of 2025-11-09)
  - Note: WorkflowClassifier removed - Config metadata will handle validation
  - See: DEVELOPMENT_DECISIONS.md (2025-10-28) for Inpainting implementation plan
- [ ] Inpainting support
  - Note: Requires image_text_media_generation pipeline + inpainting config
- [ ] ControlNet support
- [ ] Video generation support
- [ ] Seed persistence and regeneration UI
  - Status: Backend ready (stage4_only), frontend postponed

### Phase 3: Additional Backends
- [ ] Replicate API integration
- [ ] Stability AI API
- [ ] Direct OpenAI DALL-E integration
- [ ] GPT-5 Image via OpenRouter (fast mode)

### Phase 4: Optimization
- [ ] Batch processing (multiple prompts → multiple images)
- [ ] Streaming output (real-time generation progress via SSE)
- [ ] Cost optimization (choose cheapest model for task)
- [ ] Fallback chains (try model A, if fails try model B)
- [ ] Enhanced caching strategies

### Phase 5: Field Testing & Stabilization
- [ ] Extensive workshop field testing
- [ ] Performance benchmarking
- [ ] Edge case handling
- [ ] Documentation refinement
- [ ] Beta release preparation

---

## Notes

**Alpha Designation:** v2.0.0-alpha.1 represents first fully functional release with core features operational. Advanced features (SSE, seed UI) postponed for field testing and stabilization.

**Migration Path:** The architecture with LivePipelineRecorder as single source of truth provides a solid foundation for future enhancements.

