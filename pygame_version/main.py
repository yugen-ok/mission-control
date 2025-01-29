"""
Connection codes:

0: default
1: noise factor=.75

2: window
3: locked

"""

import argparse

from entities import *
from gameworld import *
from GUI import GUI


# Helper function to find key areas (areas with multiple connections)
def get_key_areas(areas_dict):
    key_areas = []
    for area_id, area in areas_dict.items():
        # Count only non-window connections
        valid_connections = [conn for conn in area.connections
                             if conn.conn_type != 'window']
        if len(valid_connections) >= 2:
            key_areas.append(area_id)
    return key_areas


def add_template_guards(areas_dict, config, world):
    """
    Add template guards with randomized patrol routes.

    Args:
        areas_dict: Dictionary of Area objects
        config: Mission configuration dictionary containing template guard settings
        world: World instance for creating Hostile entities
    """
    n_guards = config.get("n_template_guards", 0)
    if n_guards == 0:
        return []

    # Determine number of stationary guards (30% of total)
    n_stationary = max(1, int(n_guards * 0.3))
    n_patrolling = n_guards - n_stationary

    hostiles = []
    guard_stats = config.get("template_guard_stats", {})
    logger.debug(f"Template guard stats from config: {guard_stats}")

    # Helper function to generate a patrol route
    def generate_patrol_route(start_area_id, length):
        route = [start_area_id]
        current_area = areas_dict[start_area_id]
        attempts = 0

        while len(route) < length and attempts < 20:
            # Get connected areas
            connected_areas = []
            for conn in current_area.connections:
                other_area = conn.get_other_area(current_area)
                # Skip windows and sight-only connections
                if conn.conn_type != 'window' and not conn.sight_only:
                    for area_id, area in areas_dict.items():
                        if area == other_area:
                            connected_areas.append(area_id)
                            break

            if not connected_areas:
                break

            next_area_id = random.choice(connected_areas)
            # Avoid immediate backtracking unless necessary
            if len(connected_areas) > 1 and next_area_id == route[-2] if len(route) > 1 else False:
                attempts += 1
                continue

            route.append(next_area_id)
            current_area = areas_dict[next_area_id]
            attempts = 0

        return route

    # Place stationary guards at key positions
    key_areas = get_key_areas(areas_dict)
    stationary_positions = random.sample(key_areas, min(n_stationary, len(key_areas)))

    # Create stationary guards
    for i, area_id in enumerate(stationary_positions):
        guard_data = {
            "name": f"Guard {i + 1}",
            "description": "",
            "patrol_route": [areas_dict[area_id]],  # Single area for stationary guards
            **guard_stats
        }
        logger.debug(f"Creating guard with data: {guard_data}")
        hostile = Hostile(**guard_data, world=world)
        logger.debug(f"Guard created with skills: {hostile.skills}")
        hostiles.append(hostile)

    # Create patrolling guards
    for i in range(n_patrolling):
        start_area = random.choice(key_areas)
        patrol_route = generate_patrol_route(start_area, length=random.randint(3, 6))

        guard_data = {
            "name": f"Guard {i + n_stationary + 1}",
            "description": "",
            "patrol_route": [areas_dict[area_id] for area_id in patrol_route],
            **guard_stats
        }
        hostile = Hostile(**guard_data, world=world)
        logger.debug(f"Guard initial skills: {hostile.skills}")

        hostiles.append(hostile)
    return hostiles


def main(config_path, mode, agents_hidden, hostiles_visible):
    # Load configuration from JSON file
    global noise_factor
    with open(config_path, "r") as file:
        config = json.load(file)

    # Instantiate the world
    world = World()

    # Create areas
    areas = {}
    for area_id, area_data in config["areas"].items():

        p = random.random()
        if p < AREA_MOD_PROB:
            cover_modifier = hiding_modifier = .1
            desc_add = " Offers some extra cover"
        elif p < AREA_MOD_PROB * 2:
            cover_modifier = hiding_modifier = -.1
            desc_add = " Offers relatively little cover"
        else:
            cover_modifier = hiding_modifier = 0
            desc_add = ""

        area = Area(
            name=area_data["name"],
            x=area_data["x"],
            y=area_data["y"],
            width=area_data["width"],
            height=area_data["height"],
            color=area_data["color"],
            image=area_data.get("image", None),
            description=area_data["description"] + desc_add,
            hiding_modifier=area_data.get("hiding_modifier", hiding_modifier),
            cover_modifier=area_data.get("cover_modifier", cover_modifier),
            noise_baseline=area_data.get("noise_baseline", 0),
            explored=area_data.get("explored", 0),
            is_extraction_point=area_data.get("is_extraction_point", False),
            world=world
        )

        # TODO: parametrize
        if area.width * area.height < 7000:
            area.hiding_modifier -= .4
            area.cover_modifier -= .4

        if 's' in area_id:
            area.is_extraction_point = True

        areas[area_id] = area

    # Connect areas
    for area_id, area_data in config["areas"].items():
        for conn, conn_type in area_data["connections"].items():

            if conn_type == 0:
                areas[area_id].connect_open(areas[conn])
            elif conn_type == 1:
                areas[area_id].connect_door(areas[conn])
            elif conn_type == 2:
                areas[area_id].connect_window(areas[conn])

    # Instantiate characters

    for agent_data in config["agents"]:
        area = areas[agent_data.pop("area")]
        Agent(**agent_data, area=area, world=world)

    for hostile_data in config["hostiles"]:
        hostile_data["patrol_route"] = list(map(lambda x: areas[x], hostile_data.pop("patrol_route")))
        Hostile(**hostile_data, world=world)

    for objective_data in config["objectives"]:
        area_data = objective_data.pop("area", None)

        if area_data:
            # Use the specified area directly if provided in the configuration
            selected_area = areas[area_data]
        else:
            # Randomize an area while maximizing distance from other objectives
            candidate_areas = [area for area_id, area in areas.items() if area_id.startswith("r")]

            if not candidate_areas:
                raise ValueError("No valid candidate areas found for objectives.")

            objectives = [entity for entity in world.entity_registry.values() if isinstance(entity, Objective)]
            if not objectives:
                # If no objectives have been placed yet, choose a random starting area
                selected_area = random.choice(candidate_areas)
            else:
                # Select an area from the top k farthest areas
                chosen_areas = [objective.area for objective in objectives]
                top_k_areas = find_top_k_farthest_areas(candidate_areas, chosen_areas, k=4)
                selected_area = random.choice(top_k_areas)

        # Create and assign the objective to the selected area
        Objective(**objective_data, area=selected_area, world=world)

    add_template_guards(areas, config, world)

    # Create the GameMap instance
    game_map = GameMap(areas=list(areas.values()))

    # Create the GameController instance
    gc = GameController(world=world, game_map=game_map, mode=mode, agents_hidden=agents_hidden,
                        hostiles_visible=hostiles_visible)

    gui = GUI(config_path, gc)
    gui.run()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the game with specified configuration.")
    parser.add_argument(
        "config_path",
        type=str,
        nargs="?",
        default="mission_configs/mission_config.json",
        help="Path to the mission configuration JSON file (default: mission_configs/mission_config.json)."
    )
    parser.add_argument(
        "-m", "--mode", type=str, nargs="?", default='auto',
        help="Choose decision making mode (Options: [auto (a), semi-auto (sa), manual (m), test (t)]), (default: auto)."
    )
    parser.add_argument(
        "-ah", "--agents-hidden", action="store_true", help="Set agents to always be hidden (default: False)."
    )
    parser.add_argument(
        "-hv", "--hostiles-visible", action="store_true", help="Set hostiles to always be visible (default: False)."
    )

    args = parser.parse_args()

    main(
        config_path=args.config_path,
        mode=args.mode,
        agents_hidden=args.agents_hidden,
        hostiles_visible=args.hostiles_visible
    )
