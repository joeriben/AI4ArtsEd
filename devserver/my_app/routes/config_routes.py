"""
Flask routes for configuration
"""
import logging
from flask import Blueprint, jsonify, request

logger = logging.getLogger(__name__)

# Create blueprint
config_bp = Blueprint('config', __name__)


@config_bp.route('/api/models/availability', methods=['GET'])
def get_model_availability():
    """
    Check availability of models across all backends (ComfyUI, GPU service, cloud APIs).

    Each backend is checked independently — ComfyUI being down does NOT prevent
    Diffusers/HeartMuLa configs from being reported as available.

    Query Parameters:
        force_refresh (bool): If true, bypass cache and query fresh

    Returns:
        JSON response with availability map:
        {
            "status": "success",
            "availability": {
                "flux2_diffusers": true,
                "sd35_large": false,
                "heartmula_standard": true
            },
            "account_missing": ["gemini_3_pro_image"],
            "account_provider": {"gemini_3_pro_image": "mammouth"},
            "comfyui_reachable": false,
            "gpu_service_reachable": true,
            "cached": false,
            "cache_age_seconds": 0
        }
    """
    try:
        from my_app.services.model_availability_service import ModelAvailabilityService

        from my_app.services.own_loop import run_blocking

        force_refresh = request.args.get('force_refresh', 'false').lower() == 'true'
        service = ModelAvailabilityService()

        if force_refresh:
            service.invalidate_caches()
        availability = run_blocking(service.check_all_configs())
        gpu_status = run_blocking(service.get_gpu_service_status())

        return jsonify({
            "status": "success",
            "availability": availability,
            # The cloud configs among the unavailable ones whose provider holds
            # no key, refuses it, or reports no credit left: a surface names that
            # cause instead of the one for a model that is not installed.
            "account_missing": sorted(service.account_missing),
            # config id -> the provider it sends to, for each of those: the
            # sentence a surface shows names it.
            "account_provider": dict(sorted(service.account_provider.items())),
            "comfyui_reachable": service._is_comfyui_reachable(),
            "gpu_service_reachable": gpu_status.get("gpu_service_reachable", False),
            "cached": service._is_cache_valid() or service._is_gpu_cache_valid(),
            "cache_age_seconds": service._get_cache_age()
        })

    except Exception as e:
        logger.error(f"[MODEL_AVAILABILITY] Error checking model availability: {e}")
        return jsonify({
            "status": "error",
            "error": str(e),
            "availability": {},
            "account_missing": [],
            "account_provider": {},
            "comfyui_reachable": False,
            "gpu_service_reachable": False
        }), 500
