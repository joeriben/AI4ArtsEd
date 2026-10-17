#!/usr/bin/env python3
"""
Test Output-Pipeline direkt: single_text_media_generation mit sd35_large
Testet das Proxy-Chunk-System ohne Interception-Pipeline
"""
import asyncio
import sys
import logging
from pathlib import Path

# Setup paths
devserver_path = Path(__file__).parent
schemas_path = devserver_path / "schemas"
sys.path.insert(0, str(devserver_path))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_output_pipeline():
    """Test direct Output-Pipeline execution"""
    try:
        from schemas.engine.pipeline_executor import PipelineExecutor

        logger.info("=" * 80)
        logger.info("TEST: Direct Output-Pipeline (sd35_large)")
        logger.info("=" * 80)

        # Initialize executor
        executor = PipelineExecutor(schemas_path)
        executor.initialize()

        # Test parameters
        config_name = "sd35_large"
        input_prompt = "A majestic dragon flying over a mountain landscape at sunset, digital art, highly detailed"

        logger.info(f"Config: {config_name}")
        logger.info(f"Prompt: {input_prompt}")
        logger.info("")

        # Execute pipeline
        logger.info("Executing pipeline...")
        result = await executor.execute_pipeline(
            config_name=config_name,
            input_text=input_prompt,
            user_input=input_prompt,
        )

        # Display results
        logger.info("")
        logger.info("=" * 80)
        logger.info("RESULT")
        logger.info("=" * 80)
        logger.info(f"Status: {result.status.value}")
        logger.info(f"Success: {result.success}")
        logger.info(f"Execution Time: {result.execution_time:.2f}s")
        logger.info(f"Steps: {len(result.steps)}")

        if result.error:
            logger.error(f"Error: {result.error}")

        # Display step details
        for i, step in enumerate(result.steps, 1):
            logger.info(f"\nStep {i}: {step.chunk_name}")
            logger.info(f"  Status: {step.status.value}")

            if step.metadata:
                logger.info(f"  Metadata:")
                for key, value in step.metadata.items():
                    if key == 'workflow':
                        logger.info(f"    {key}: <workflow with {len(value)} nodes>")
                    elif isinstance(value, str) and len(value) > 100:
                        logger.info(f"    {key}: {value[:100]}...")
                    else:
                        logger.info(f"    {key}: {value}")

            if step.error:
                logger.error(f"  Error: {step.error}")

            if step.output_data:
                logger.info(f"  Output: {step.output_data[:200]}...")

        # Final output
        if result.final_output:
            logger.info(f"\nFinal Output: {result.final_output}")

        # Check if ComfyUI workflow was submitted
        if result.success and result.metadata:
            logger.info("\nPipeline Metadata:")
            for key, value in result.metadata.items():
                logger.info(f"  {key}: {value}")

        logger.info("\n" + "=" * 80)

        if result.success:
            logger.info("✓ TEST PASSED: Output-Pipeline executed successfully")

            # Check specific success criteria
            if result.steps:
                last_step = result.steps[-1]
                if last_step.metadata.get('comfyui_available') is False:
                    logger.warning("⚠ ComfyUI not available - workflow prepared but not submitted")
                    logger.info("  This is OK for testing the Proxy-Chunk system")
                elif last_step.metadata.get('prompt_id'):
                    logger.info(f"✓ Workflow submitted to ComfyUI: {last_step.metadata['prompt_id']}")
                elif last_step.metadata.get('submitted'):
                    logger.info("✓ Workflow submitted to ComfyUI queue")
        else:
            logger.error("✗ TEST FAILED: Pipeline execution failed")

        logger.info("=" * 80)

        return result

    except Exception as e:
        logger.error(f"Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    result = asyncio.run(test_output_pipeline())
    sys.exit(0 if result and result.success else 1)
