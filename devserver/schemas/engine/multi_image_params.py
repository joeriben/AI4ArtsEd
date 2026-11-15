"""The images a multi-image run hands over: input_image1, input_image2, ...

MAX_MULTI_IMAGES is the most any chunk takes (FLUX 3 Image Klein names ten
references). How many a given run may fill is the chunk's own input_mappings;
the numbers below that are simply not asked for.
"""

MAX_MULTI_IMAGES = 10
MULTI_IMAGE_KEYS = tuple(f'input_image{n}' for n in range(1, MAX_MULTI_IMAGES + 1))


def multi_images_from(source) -> dict:
    """The multi-image parameters a request carries, in order, empty ones left out."""
    return {key: source.get(key) for key in MULTI_IMAGE_KEYS if source.get(key)}
