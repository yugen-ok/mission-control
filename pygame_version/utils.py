
import math
import uuid
import hashlib
import threading
import networkx as nx
from constants import *

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
    smaller_int = int(hash_object.hexdigest(), 16) % (10**18)  # Reduce size

    return smaller_int

