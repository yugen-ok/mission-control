import math
import uuid
import hashlib
import threading
import networkx as nx
from uuid import UUID

from constants import *


def safe_uuid_conversion(arg):
    try:
        return UUID(arg)
    except ValueError:
        # Find the closest matching valid UUID from your valid_args list
        # Or log the error and continue with retry logic
        return None


# Helper function to calculate the distance between two areas
def calculate_distance(area1, area2):
    dx = area1.x - area2.x
    dy = area1.y - area2.y
    return math.sqrt(dx * dx + dy * dy)


# Find the top k areas farthest from all previously chosen areas
def find_top_k_farthest_areas(candidate_areas, chosen_areas, k=4):
    area_distances = []

    for candidate_area in candidate_areas:
        # Calculate the minimum distance from this candidate area to all chosen areas
        min_distance = float("inf")
        for chosen_area in chosen_areas:
            distance = calculate_distance(candidate_area, chosen_area)
            if distance < min_distance:
                min_distance = distance

        # Store the candidate area and its minimum distance
        area_distances.append((candidate_area, min_distance))

    # Sort areas by minimum distance in descending order
    area_distances.sort(key=lambda x: x[1], reverse=True)

    # Return the top k areas
    return [area for area, _ in area_distances[:k]]


def inputt(prompt, timeout):
    user_input = []

    def inner_input():
        user_input.append(input(prompt))

    thread = threading.Thread(target=inner_input)
    thread.daemon = True
    thread.start()
    thread.join(timeout)

    if thread.is_alive():
        # If the input timed out, just return a blank string
        return ""
    else:
        return user_input[0]


def encode_uuids_to_integer(*uuids: uuid.UUID) -> int:
    """
    Encodes an arbitrary number of UUID objects into a smaller unique integer.

    Args:
        *uuids (uuid.UUID): UUID objects to encode.

    Returns:
        int: A smaller unique integer representing the combined UUIDs.
    """
    combined_int = 0

    for u in uuids:
        # Shift the current combined integer by 128 bits and add the next UUID's integer
        combined_int = (combined_int << 128) | u.int

    # Hash the combined integer to produce a smaller integer
    hash_object = hashlib.sha256(str(combined_int).encode())
    smaller_int = int(hash_object.hexdigest(), 16) % (10 ** 18)  # Reduce size

    return smaller_int
