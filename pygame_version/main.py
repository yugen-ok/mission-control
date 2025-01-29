
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
            cover_modifier=area_data.get("cover_modifierr", cover_modifier),
            noise_baseline=area_data.get("noise_baseline", 0),
            explored=area_data.get("explored", 0),
            is_extraction_point=area_data.get("is_extraction_point", False),
            world=world
        )
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
    # Consider splitting into agents, hostiles, civilians, etc
    agents = []
    hostiles = []
    for agent_data in config["agents"]:
        area = areas[agent_data.pop("area")]
        agent = Agent(**agent_data, area=area, world=world)

        agents.append(agent)

    for hostile_data in config["hostiles"]:
        hostile_data["patrol_route"] = list(map(lambda x: areas[x], hostile_data.pop("patrol_route")))
        hostile = Hostile(**hostile_data, world=world)
        hostiles.append(hostile)

    for objective_data in config["objectives"]:
        area = areas[objective_data.pop("area")]
        objective = Objective(**objective_data, area=area, world=world)

    # Create the GameMap instance
    game_map = GameMap(areas=list(areas.values()))

    # Create the GameController instance
    gc = GameController(world=world, game_map=game_map, mode=mode, agents_hidden=agents_hidden, hostiles_visible=hostiles_visible)

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
