
import uuid
import hashlib

import networkx as nx


# TODO:
# For efficiency, store entities in a hierarchical structure


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

class World:
    def __init__(self, default_connection='A door'):
        # Maps entity_id (UUID) to exploration level
        self.exploration_levels = {}
        # Maps entity_id (UUID) to entity objects for easy lookup
        self.entity_registry = {}
        self.default_connection = default_connection

    def describe_connection(self, connection_description):
        """A function to describe a connection between areas if they are empty."""
        if not connection_description:
            return self.default_connection
        return connection_description

    def add_entity(self, entity):
        """Add an entity to the world."""
        self.exploration_levels[entity.id] = entity.get_explored()
        self.entity_registry[entity.id] = entity

    def entity_registry_string(self):
        out = ''
        for id, entity in self.entity_registry.items():
            out += f'{id}: {entity.name}\n'
        return out

    def remove_entity(self, entity):
        """Safely remove an entity from the world and all areas."""
        # First remove from area to prevent any references
        if entity.area and entity in entity.area.entities:
            entity.area.entities.remove(entity)

        # Then remove from registries
        self.exploration_levels.pop(entity.id, None)  # Using pop with None default to avoid KeyError
        self.entity_registry.pop(entity.id, None)  # Using pop with None default to avoid KeyError

    def update_exploration(self, entity_id, level):
        """Update the exploration level of an entity."""
        self.exploration_levels[entity_id] = level

    def get_explored_entities(self):
        """Return all explored entities."""
        return {entity_id: level for entity_id, level in self.exploration_levels.items() if level > 0}

    def get_entity_by_id(self, entity_id):
        """Retrieve an entity by its UUID."""
        return self.entity_registry.get(entity_id, None)

    def get_entities_above_exploration(self, level):
        """Return all entities with an exploration level higher than the given level."""
        return {entity_id: self.entity_registry[entity_id] for entity_id, exploration_level in
                self.exploration_levels.items() if exploration_level > level}

class GameMap:
    def __init__(self, areas):
        self.areas = areas  # List of all Area objects
        self.id_to_area = {area.id: area for area in areas}  # Map IDs to area objects
        self.build_graph()

    def build_graph(self):
        # Create the graph using IDs instead of names
        graph = nx.Graph()
        for area in self.areas:
            graph.add_node(area.id)  # Use ID as the node
            for connected_area in area.get_connected_areas():
                graph.add_edge(area.id, connected_area.id)  # Use IDs for edges

        self.graph = graph

    def get_shortest_path(self, start_area, target_area, return_names=False):
        """
        Get the shortest path (as a list of area IDs or names) between two areas in the map.

        Args:
            start_area_id (UUID): The ID of the starting area.
            target_area_id (UUID): The ID of the target area.
            return_names (bool): Whether to return area names instead of IDs.

        Returns:
            list: A list of area IDs or names representing the shortest path.
        """

        start_area_id = start_area.id
        target_area_id = target_area.id

        try:
            # Find the shortest path using NetworkX
            shortest_path_ids = nx.shortest_path(self.graph, source=start_area_id, target=target_area_id)

            if return_names:
                # Convert IDs to names
                return [self.id_to_area[area_id] for area_id in shortest_path_ids]

            shortest_path = [self.id_to_area[area_id] for area_id in shortest_path_ids]

            return shortest_path
        except nx.NetworkXNoPath:
            return None  # No path exists between the areas
        except KeyError:
            return None  # One or both of the IDs are not in the graph

    def get_area_by_id(self, area_id):
        """
        Retrieve the area object corresponding to the given ID.
        """
        return self.id_to_area.get(area_id, None)