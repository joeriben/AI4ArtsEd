"""
Blender Headless Render Script — GLB to PNG Preview

This script is executed by Blender's embedded Python interpreter, NOT the venv.
It is invoked as: blender --background --python render_mesh.py -- config.json

The config JSON contains all rendering parameters.

Renders a GLB mesh with Eevee for fast, high-quality preview images.
"""

import sys
import json
import math

# Blender modules (only available inside Blender's Python)
import bpy
import mathutils


def clear_scene():
    """Remove all default objects from the scene."""
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)

    # Also clear orphan data
    for collection in [bpy.data.meshes, bpy.data.materials, bpy.data.textures,
                       bpy.data.images, bpy.data.cameras, bpy.data.lights]:
        for item in collection:
            collection.remove(item)


def import_glb(glb_path):
    """Import a GLB file into the scene."""
    bpy.ops.import_scene.gltf(filepath=glb_path)

    # Get all imported mesh objects
    imported = [obj for obj in bpy.context.selected_objects if obj.type == 'MESH']
    if not imported:
        # Try all objects
        imported = [obj for obj in bpy.data.objects if obj.type == 'MESH']

    return imported


def center_and_normalize(objects):
    """Center imported objects and normalize to unit scale."""
    if not objects:
        return

    # Calculate bounding box of all objects combined
    min_coords = [float('inf')] * 3
    max_coords = [float('-inf')] * 3

    for obj in objects:
        for vertex in obj.bound_box:
            world_coord = obj.matrix_world @ mathutils.Vector(vertex)
            for i in range(3):
                min_coords[i] = min(min_coords[i], world_coord[i])
                max_coords[i] = max(max_coords[i], world_coord[i])

    # Calculate center and size
    center = [(min_coords[i] + max_coords[i]) / 2 for i in range(3)]
    size = max(max_coords[i] - min_coords[i] for i in range(3))

    if size == 0:
        size = 1.0

    # Normalize scale and center
    scale_factor = 2.0 / size
    for obj in objects:
        obj.location[0] -= center[0]
        obj.location[1] -= center[1]
        obj.location[2] -= center[2]
        obj.scale *= scale_factor


def setup_camera(distance=2.5, elevation=30.0, azimuth=45.0):
    """Set up camera looking at origin from given spherical coordinates."""
    # Convert angles to radians
    elev_rad = math.radians(elevation)
    azim_rad = math.radians(azimuth)

    # Spherical to Cartesian
    x = distance * math.cos(elev_rad) * math.cos(azim_rad)
    y = distance * math.cos(elev_rad) * math.sin(azim_rad)
    z = distance * math.sin(elev_rad)

    # Create camera
    cam_data = bpy.data.cameras.new('RenderCamera')
    cam_data.lens = 50
    cam_data.clip_start = 0.1
    cam_data.clip_end = 100.0

    cam_obj = bpy.data.objects.new('RenderCamera', cam_data)
    bpy.context.collection.objects.link(cam_obj)

    cam_obj.location = (x, y, z)

    # Point camera at origin
    direction = mathutils.Vector((0, 0, 0)) - cam_obj.location
    rot_quat = direction.to_track_quat('-Z', 'Y')
    cam_obj.rotation_euler = rot_quat.to_euler()

    bpy.context.scene.camera = cam_obj
    return cam_obj


def setup_lighting(light_type="three_point"):
    """Set up scene lighting."""
    if light_type == "three_point":
        # Key light (warm, strong)
        key = bpy.data.lights.new('KeyLight', 'AREA')
        key.energy = 200
        key.color = (1.0, 0.95, 0.9)
        key.size = 2.0
        key_obj = bpy.data.objects.new('KeyLight', key)
        key_obj.location = (3, -2, 4)
        key_obj.rotation_euler = (math.radians(45), 0, math.radians(30))
        bpy.context.collection.objects.link(key_obj)

        # Fill light (cool, softer)
        fill = bpy.data.lights.new('FillLight', 'AREA')
        fill.energy = 80
        fill.color = (0.85, 0.9, 1.0)
        fill.size = 3.0
        fill_obj = bpy.data.objects.new('FillLight', fill)
        fill_obj.location = (-3, -1, 2)
        fill_obj.rotation_euler = (math.radians(30), 0, math.radians(-30))
        bpy.context.collection.objects.link(fill_obj)

        # Rim light (accent from behind)
        rim = bpy.data.lights.new('RimLight', 'AREA')
        rim.energy = 120
        rim.color = (1.0, 1.0, 1.0)
        rim.size = 1.5
        rim_obj = bpy.data.objects.new('RimLight', rim)
        rim_obj.location = (-1, 3, 3)
        rim_obj.rotation_euler = (math.radians(60), 0, math.radians(150))
        bpy.context.collection.objects.link(rim_obj)

    elif light_type == "studio":
        # Single strong area light from above
        light = bpy.data.lights.new('StudioLight', 'AREA')
        light.energy = 300
        light.color = (1.0, 1.0, 1.0)
        light.size = 5.0
        light_obj = bpy.data.objects.new('StudioLight', light)
        light_obj.location = (0, 0, 5)
        light_obj.rotation_euler = (0, 0, 0)
        bpy.context.collection.objects.link(light_obj)

    else:
        # Ambient: HDRI-like via sun + hemisphere
        sun = bpy.data.lights.new('SunLight', 'SUN')
        sun.energy = 3
        sun.color = (1.0, 0.98, 0.95)
        sun_obj = bpy.data.objects.new('SunLight', sun)
        sun_obj.location = (0, 0, 10)
        sun_obj.rotation_euler = (math.radians(45), 0, math.radians(30))
        bpy.context.collection.objects.link(sun_obj)


def setup_background(hex_color="#0a0a0a"):
    """Set world background color."""
    world = bpy.data.worlds.new('RenderWorld')
    bpy.context.scene.world = world
    world.use_nodes = True

    bg_node = world.node_tree.nodes.get('Background')
    if bg_node:
        # Parse hex color
        hex_color = hex_color.lstrip('#')
        r = int(hex_color[0:2], 16) / 255.0
        g = int(hex_color[2:4], 16) / 255.0
        b = int(hex_color[4:6], 16) / 255.0
        bg_node.inputs['Color'].default_value = (r, g, b, 1.0)
        bg_node.inputs['Strength'].default_value = 1.0


def setup_render(resolution=1024, output_path="render.png"):
    """Configure Eevee render settings."""
    scene = bpy.context.scene

    # Use Eevee for fast rendering
    scene.render.engine = 'BLENDER_EEVEE_NEXT' if bpy.app.version >= (4, 0, 0) else 'BLENDER_EEVEE'

    scene.render.resolution_x = resolution
    scene.render.resolution_y = resolution
    scene.render.resolution_percentage = 100

    # Output settings
    scene.render.filepath = output_path
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGBA'
    scene.render.image_settings.compression = 15

    # Eevee quality settings
    scene.render.film_transparent = True  # Transparent background (alpha)

    # Anti-aliasing
    if hasattr(scene.eevee, 'taa_render_samples'):
        scene.eevee.taa_render_samples = 64


def main():
    # Parse config from command line args (after --)
    argv = sys.argv
    config_path = None

    if '--' in argv:
        args_after = argv[argv.index('--') + 1:]
        if args_after:
            config_path = args_after[0]

    if not config_path:
        print("ERROR: No config file provided. Usage: blender --background --python render_mesh.py -- config.json")
        sys.exit(1)

    # Load config
    with open(config_path, 'r') as f:
        config = json.load(f)

    glb_path = config['glb_path']
    output_path = config['output_path']

    print(f"[RENDER] GLB: {glb_path}")
    print(f"[RENDER] Output: {output_path}")

    # Setup scene
    clear_scene()
    objects = import_glb(glb_path)

    if not objects:
        print("ERROR: No mesh objects found in GLB file")
        sys.exit(1)

    print(f"[RENDER] Imported {len(objects)} mesh objects")

    center_and_normalize(objects)
    setup_camera(
        distance=config.get('camera_distance', 2.5),
        elevation=config.get('camera_elevation', 30.0),
        azimuth=config.get('camera_azimuth', 45.0),
    )
    setup_lighting(config.get('light_type', 'three_point'))
    setup_background(config.get('background_color', '#0a0a0a'))
    setup_render(
        resolution=config.get('resolution', 1024),
        output_path=output_path,
    )

    # Render
    print("[RENDER] Starting Eevee render...")
    bpy.ops.render.render(write_still=True)
    print(f"[RENDER] Done: {output_path}")


if __name__ == '__main__':
    main()
