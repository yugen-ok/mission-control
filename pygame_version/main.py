import json
import argparse

from entities import *
from gameworld import *
from GUI import GUI

def main(config_path, test_mode, agents_hidden, hostiles_visible):
    # Load configuration from JSON file
    with open(config_path, "r") as file:
        config = json.load(file)

    # Instantiate the world
    world = World()

    # Create areas
    areas = {}
    for area_id, area_data in config["areas"].items():
        area = Area(
            name=area_data["name"],
            x=area_data["x"],
            y=area_data["y"],
            width=area_data["width"],
            height=area_data["height"],
            color=area_data["color"],
            image=area_data.get("image", None),
            description=area_data["description"],
            hiding_bonus=area_data.get("hiding_bonus", 0),
            cover_bonus=area_data.get("cover_bonus", 0),
            noise_baseline=area_data.get("noise_baseline", 0),
            explored=area_data.get("explored", 0),
            is_extraction_point=area_data.get("is_extraction_point", False),
            world=world
        )
        areas[area_id] = area

    # Connect areas
    for area_id, area_data in config["areas"].items():
        for connection in area_data["connections"]:
            if connection in areas:
                areas[area_id].connect(areas[connection])

    # Instantiate characters
    # Consider splitting into agents, hostiles, civilians, etc
    characters = []
    for character_data in config["characters"]:
        char_type = character_data.pop("type")
        area = areas[character_data.pop("area")]

        if char_type == "agent":
            character = Agent(**character_data, area=area, world=world)
        elif char_type == "hostile":
            character_data["patrol_route"] = list(map(lambda x: areas[x], character_data.pop("patrol_route")))
            character = Hostile(**character_data, world=world)
        else:
            raise ValueError(f"Unknown character type: {char_type}")

        characters.append(character)

    for objective_data in config["objectives"]:
        area = areas[objective_data.pop("area")]
        objective = Objective(**objective_data, area=area, world=world)

    # Create the GameMap instance
    game_map = GameMap(areas=list(areas.values()))

    # Create the GameController instance
    gc = GameController(world=world, game_map=game_map, test_mode=test_mode, agents_hidden=agents_hidden, hostiles_visible=hostiles_visible)

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
        "-t", "--test-mode", action="store_true", help="Enable test mode (default: False)."
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
        test_mode=args.test_mode,
        agents_hidden=args.agents_hidden,
        hostiles_visible=args.hostiles_visible
    )
