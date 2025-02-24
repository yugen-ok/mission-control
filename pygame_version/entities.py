from bidict import bidict
from pprint import pprint
import random
import json

from ai_response_tools import *
from chaos import *
from utils import *

from collections import deque
import uuid
from uuid import UUID
from typing import List
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Note: right now, when an agent moves into a room, entities they detect are auto added to the minimap,
# but not described in the log unless you ask about them. This is to avoid swamping the log,
# so we can imagine as if such entities are reported by the agents and instead of being printed into the log they are just mentioned in the minimap.

"""Feature Conv: 
https://chatgpt.com/share/6772d99b-cb78-800e-996b-810c66da2375"""

global has_reached_th


# TODO:

# - Enemy communication
# - Agent smarter behavior
# - Manual mode from GUI
# - improve takeout mechanics
# - Disguises
# - Stealth shots across rooms
# - Parametrize area modifiers as a funciton of geometric area
# - mark connections with access difficulty on the map
# - test hostile chase and extended patrol break
# - cameras and cctv disable
# - locks, lockpicking, keys, unlock with hacking
# - Connections that require acrobatics
# - Silent ranged attacks
# - cover and hiding as area properties instead of entities
# - Allow hostiles to attack with hand-to-hand in certain cases
# - Vary cover/hiding bonus within an area (meaning it is not the same for all chars in the area)
# - Allow to spot connections while peeking
# - smoke/flashbang/noise grenades (+ protective goggles/headset)
# - peek makes more noise in ajacent areas
# - implement psychology: resilience
# - Agent personalities
# - stabilize wounded agents
# - carry bodies
# - some agents want to do more, so if you tell them to stand down they might go in anyway
# - Add Hostile subclasses: guard, technician, janitor, etc.

def get_corresponding_value(val, threshold_map):
    # Sort thresholds in ascending order
    sorted_thresholds = sorted(threshold_map.keys())

    # Find the largest threshold <= value1
    for threshold in reversed(sorted_thresholds):
        if val >= threshold:
            return threshold_map[threshold]

    raise ValueError(f"Value {val} is not within the threshold range.")


class ConnectivityException(Exception):
    pass


class Entity:
    def __init__(self, name, area, description, explored=0, world=None, spot_difficulty=0, investigate_difficulty=0):
        self.id = uuid.uuid4()  # Assign a unique ID to each entity
        self.name = name  # Name or identifier
        self.area = area  # Current area
        self.description = description
        self._explored = explored
        self.world = world  # Reference to the world instance
        self.spot_difficulty = spot_difficulty  # Difficulty in spotting the entity in the area
        self.investigate_difficulty = investigate_difficulty  # Difficulty in investigating the entity

        # This is an inelegant way to achieve this
        # TODO: improve
        self.is_peeked = False

        # Register the entity with the world instance
        if self.world:
            self.world.add_entity(self)

    def get_description(self):
        """
        This is not the entity's actaul description. It's the way it would be described pragmatically given the current exploration level.
        """
        if self._explored == 0:
            desc = self.description
            if desc and desc[-1] == '.':
                desc = desc[:-1]
                return f"{self.name} ({desc})"
            return self.name
        elif self._explored == 1:
            return f"the {self.name}"
        elif self._explored == 2:
            return ''

    def get_explored(self):
        return self._explored

    def set_explored(self, level):
        if level != self._explored:
            self._explored = level
            # Update the exploration level in the world dictionary
            if self.world:
                self.world.update_exploration(self.id, level)

    def __str__(self):
        return f"{self.name}: {self.description}"

    def __repr__(self):
        return f"{self.name}: {self.description}"


class Character(Entity):
    def __init__(self, name, area, health=1., resilience=.5, stealth=0., firearms=0., cover=0., hand_to_hand=0.,
                 hacking=0.,
                 observation=0.,
                 acrobatics=0., inventory=None, description='', behavior='', explored=2, world=None):
        super().__init__(name, area, description, explored=explored, world=world)

        if inventory is None:
            inventory = []

        self.health = self.max_health = max(0., min(health, 1.))
        self.stress_level = 0.
        self.resilience = max(0., min(resilience, 1.))

        self.skills = {
            "stealth": max(0., min(stealth, 1.)),
            "firearms": max(0., min(firearms, 1.)),
            "cover": max(0., min(cover, 1.)),
            "hand_to_hand": max(0., min(hand_to_hand, 1.)),
            "hacking": max(0., min(hacking, 1)),
            "observation": max(0., min(observation, 1.)),
            "acrobatics": max(0., min(acrobatics, 1.))
        }
        self.inventory = inventory
        self.behavior = behavior


        self.knowledge_base = ''
        self.is_hidden = False

    def take_action(self, action_type, target=None, modifier=0.):
        """
        Core method to determine success of actions available to characters.

        Currently implemented actions:

            wait
            look_around
            peek
            investigate
            hide
            take_out
            shoot
            bypass
            capture
        """

        logger.debug(f"=== ACTION CHECK: {action_type} ===")
        logger.debug(f"Actor: {self.name}")

        if isinstance(target, Connection):
            target_name = "Connection with " + target.get_other_area(self.area).name
        else:
            target_name = target.name if target else 'None'

        logger.debug(f"Target: {target_name}")
        logger.debug(f"Initial modifier: {modifier}")

        skill1 = ACTION_TO_SKILL.get(action_type, None)
        logger.debug(f"Primary skill: {skill1} = {self.skills[skill1] if skill1 else 'None'}")

        # Special modifiers
        if action_type == 'peek':
            modifier += PEEK_MOD
            logger.debug(f"Added peek modifier: {PEEK_MOD}")
        elif action_type == 'investigate':
            modifier += INV_MOD
            logger.debug(f"Added investigate modifier: {INV_MOD}")

        # Calculate difficulty
        if action_type == 'wait':
            difficulty = 0.
            logger.debug("Wait action - no difficulty check")
        elif action_type in ['look_around', 'peek', 'investigate']:
            if isinstance(target, Connection):
                if action_type == 'look_around':
                    difficulty = target.get_spot_difficulty(self.area)
                elif action_type == 'peek':
                    difficulty = target.get_peek_difficulty(self.area)
                else:
                    difficulty = target.get_investigate_difficulty(self.area)
                logger.debug(f"Connection difficulty: {difficulty}")
            else:
                difficulty = target.spot_difficulty
                logger.debug(f"Spot difficulty: {difficulty}")

        elif isinstance(target, Character):
            assert action_type in ['hide', 'take_out', 'shoot']
            skill2 = ACTION_TO_COUNTER_SKILL.get(action_type, None)
            difficulty = target.skills[skill2]
            logger.debug(f"Target counter skill: {skill2} = {difficulty}")

            if action_type == 'hide':
                modifier += self.area.hiding_modifier
                logger.debug(f"Added area hiding modifier: {self.area.hiding_modifier}")
            elif action_type == 'shoot':
                # Cover modifier is inverse to shooting
                # So if it is positive, it is harder to shoot, and vice versa
                modifier -= self.area.cover_modifier
                logger.debug(f"Added area cover modifier: {self.area.cover_modifier}")

        elif action_type == 'bypass':
            difficulty = 0
            logger.debug("Bypass action - no difficulty")

        elif action_type == 'capture':
            assert isinstance(target, Objective)
            skill1 = target.required_skill
            difficulty = target.difficulty
            logger.debug(f"Objective difficulty: {difficulty}")
            logger.debug(f"Required skill: {skill1} = {self.skills[skill1]}")

        else:
            raise ValueError(f"Invalid target/action type. Target type: {type(target)}, Action type: {action_type}")

        # Calculate final probability
        raw_prob = self.skills[skill1] - difficulty + modifier
        success_prob = max(0.0, min(1.0, raw_prob))

        logger.debug(f"Probability calculation:")
        logger.debug(f"  Skill ({self.skills[skill1]:.2f}) - Difficulty ({difficulty:.2f}) + Modifier ({modifier:.2f})")
        logger.debug(f"  Raw probability: {raw_prob:.2f}")
        logger.debug(f"  Clamped probability: {success_prob:.2f}")

        roll = random.random()
        success = roll < success_prob
        logger.debug(f"Roll: {roll:.3f} vs Probability: {success_prob:.3f}")
        logger.debug(f"Result: {'SUCCESS' if success else 'FAILURE'}")
        logger.debug(f"=== ACTION CHECK END ===")

        return success


class Agent(Character):

    def status_description(self):
        """
        Generate a prompt for an AI model to summarize the agent's status and observations.
        Observations are based on entities in the same area.
        """
        objects_description = "\n".join(
            [f"{entity.name}: {entity.description}" for entity in self.area.entities]
        )

        out = 'Mission intel:\n\n' + self.knowledge_base + (
            f"\n\nYou are {self.name}, an agent in the field.\n"
            f"{self.behavior}\n"
            "Your task is to find and capture all objectives in the field, avoid detection by hostiles or neutralize them if necessary, and once all objectives have been captured, make it safely to the extraction point and exfiltrate.\n"
            "Your health and observation skills are factors in what details you can accurately notice and report. "
            f"Your health is {self.health / self.max_health:.2f}/1, and your observation skill is {self.skills['observation']:.2f}/1.\n\n"
            f"You are currently in the following area: {self.area.name} : {self.area.description}.\n"
            f"It contains the following objects: {objects_description}.\n"
            f"It is connected to the following areas: {', '.join([f'{area.name} (ID: {area.id})' for area in self.area.get_connected_areas()])}\n"

        ).format(
            health=self.health,
            observation_skill=self.skills["observation"],
            objects_description=objects_description
        )

        return out

    def generate_action_arguments(self):
        """Generate a dictionary of actions and their possible arguments."""
        action_args = {}

        action_args['wait'] = []

        accessible_areas = [area for area in self.area.get_connected_areas() if area.get_explored() > 0]

        # Peek, sneak and charge actions: require an adjacent area that is explored
        if accessible_areas:
            action_args['sneak'] = action_args['charge'] = [{'id': area.id, 'name': area.name} for
                                                                                  area in
                                                                                  accessible_areas]
            # I'm separating this forr easy switching
            # action_args['peek'] = action_args['sneak']
        # action_args['investigate'] = []

        # Shoot action: requires hostiles in the current area
        hostiles_in_area = [entity for entity in self.area.entities if isinstance(entity, Hostile)]
        if hostiles_in_area:
            action_args['shoot'] = [{'id': hostile.id, 'name': hostile.name} for hostile in
                                    hostiles_in_area]

            # Take out action: can only be taken by hidden agents
            if self.is_hidden:
                action_args['take_out'] = [{'id': hostile.id, 'name': hostile.name} for hostile in
                                           hostiles_in_area]

        # Hide action: only available to non-hidden characters in an area with no hostiles
        if not self.is_hidden and not [entity for entity in self.area.entities if isinstance(entity, Hostile)]:
            action_args['hide'] = []

        # Bypass action: requires obstacles in the current area
        obstacles_in_area = [entity for entity in self.area.entities if isinstance(entity, Obstacle)]
        if obstacles_in_area:
            action_args['bypass'] = [{'id': entity.id, 'name': entity.name} for entity in obstacles_in_area]

        # Capture action: requires objectives in the current area
        objectives_in_area = [entity for entity in self.area.entities if
                              isinstance(entity, Objective) and not entity.is_captured]
        if objectives_in_area:
            action_args['capture'] = [{'id': entity.id, 'name': entity.name} for entity in objectives_in_area]

        # Exfiltrate action: only available if the current area is an extraction point
        if self.area.is_extraction_point:
            action_args['exfiltrate'] = []

        return action_args

    def make_decision_prompt(self):
        """
        Generates a detailed prompt for an AI model to decide on the next move for the agent, given the current situation.
        The prompt includes an overview of the agent's current environment, capabilities, and a list of available actions.
        """
        status_desc = self.status_description()
        action_arguments = self.generate_action_arguments()

        available_actions_desc = (
            "Here are the actions you can take, along with their descriptions and required argument:\n"
        )

        # Describe each action with its EXACT required arguments
        # Modify this part in make_decision_prompt():
        for action, arguments in action_arguments.items():
            if arguments:
                # Show both ID and name but make it very clear which is the ID to use
                argument_details = ", ".join([f"ID {arg['id']} (of entity: {arg['name']})" for arg in arguments])
                available_actions_desc += f"- {action}: Must use one of these exact IDs - {argument_details}\n"
            else:
                available_actions_desc += f"- {action}: No argument required\n"

        instruction = (
            "Decide on your next move based on the current status, Mission Control's commands, and available actions.\n"
            "Unless Mission Control says otherwise, your goal is to "
            "You should strongly prioritize following the latest mission control commands, interpreting them to the best of your ability.\n"
            "You should interpret mission control's commands as one of the available actions as provided above.\n"
            "If unsure, use your best judgment to meet Mission Control's commands as closely as you can given the actions available to you.\n"
            "You MUST pick an action and an argument EXACTLY as listed above.\n"
            "Under no circumstance may you make an action which is not listed in the provided options above. "
            "These reprersent the actions you may take given your situation and abilities, "
            "so it is physically impossible for you to do anything else in the game world.\n"
            "Return your decision as a valid JSON dictionary object with three fields: 'action', 'arguments', and 'reasoning'.\n"
            "Your response should only include this JSON dictionary, nothing else.\n"
            "- The 'action' field should contain the name of the action you want to take.\n"
            "- The 'arguments' field should be a singleton list of the ID of the selected argument, chosen from the available arguments listed above. "
            "If no arguments are needed, return an empty list.\n"
            "- The 'reasoning' field should provide a brief explanation of why you chose this action and the specific argument.\n"
            "Ensure that your chosen arguments match the options provided for each action, if the action requires an argument.\n"
            "For actions requiring an argument, you must use one of the IDs listed above - no other IDs will work."
        )

        prompt = (
            f"{status_desc}\n\n"
            "================\n"
            "INSTRUCTIONS:\n"
            f"{available_actions_desc}\n\n"
            f"{instruction}"
        )

        return prompt

    def make_manual_decision_prompt(self):
        """
        Generates a detailed prompt for an AI model to decide on the next move for the agent, given the current situation.
        The prompt includes an overview of the agent's current environment, capabilities, and a list of available actions.
        Instead of using UUIDs for arguments, it uses integers starting from 0 and returns a mapping from those integers
        to the corresponding UUIDs. Arguments can recur across different actions.
        """

        action_arguments = self.generate_action_arguments()
        action2int_and_arg_bimap = defaultdict(dict)

        available_actions_desc = (
            "Here are the actions you can take, along with their descriptions and required arguments:\n\n"
        )

        # Describe each action along with its possible arguments
        for action, arguments in action_arguments.items():
            if arguments:
                # Map arguments to integers, reusing IDs for recurring UUIDs
                integer_arguments = []
                id_counter = 0
                for arg in arguments:
                    action2int_and_arg_bimap[action][arg['id']] = id_counter
                    action2int_and_arg_bimap[action][id_counter] = arg['id']

                    integer_arguments.append({
                        'id': id_counter,
                        'name': arg['name']
                    })
                    id_counter += 1

                # Update the description
                argument_details = ", ".join([f"{arg['id']} ({arg['name']})" for arg in integer_arguments])
                available_actions_desc += f"- {action}: Arg options - {argument_details}\n"
            else:
                available_actions_desc += f"- {action}: No arguments required\n"

        prompt = available_actions_desc

        return prompt

    def make_report_prompt(self):

        status_desc = self.status_description()

        inst = f"""

        Provide a situational report to mission control up to 200 characters. 
        Return the actual words you 
        would say in this situation. 
        Focus on the most important details. You have only a few seconds, so every word 
        counts. 
        Make the description as short and concise as possible. Do not surround your response with quotes. Do 
        not report your name. 
        When describing people, dont mention their names or their skills, but rather your 
        impression of them based on the observable facts. 
        As an agent in the field you can only see observable facts, 
        not other people's names or what they are good at. Do not report your name. Look at your area's description. 
        This is ALL the area contains. 
        Do not come up with your own ideas, stick to what is given in the description. 
        Make your response sound like what a CIA operative would actually say in this situation. Use the same type of 
        language, don't just reiterate the description your were given. Make this like a line from a tactical 
        espionage video game. 
        Use the same type of language, don't just reiterate the description your were given. 
        Don't use dashes (—), colons (:), or semicolons (;)."""

        prompt = status_desc + inst
        return prompt

    def make_answer_question_prompt(self, question):
        """
        Answer a specific question based on the current area's observations.
        """

        status_desc = self.status_description()

        inst = f"""Answer the following question by mission control: {question}
        Return the actual words you would say in this situation.
        Focus on the most important details.
        You have only a few seconds, so every word counts. Make the description as short and concise as possible.
        Do not surround your response with quotes. Do not report your name. 
        When describing people, dont mention their names or their skills, but rather your impression of them based on the observable facts. 
        As an agent in the field you can only see observable facts, not other people's names or what they are good at.
        Do not report your name.
        Don't use dashes (—), colons (:), or semicolons (;).
        Look at your area's description. This is ALL the area contains. Do not come up with your own ideas, stick to what is given in the description. 
        Make your response sound like what a CIA operative would actually say in this situation. Use the same type of language, don't just reiterate the description your were given. 
        Make this like a line from a tactical espionage video game. """

        prompt = status_desc + inst
        # print(prompt)
        # print('-------- PROMPT END ------\n\n')

        return prompt


# Hostile class
class Hostile(Character):
    """Hostile inherits the same capabilities as Agent."""

    def __init__(self, name, patrol_route,
                 health=0.6, observation=0, max_observation=.4,
                 hand_to_hand=0, max_hand_to_hand=.4,
                 firearms=0, cover=0,
                 resilience=.5, stealth=0, hacking=0, acrobatics=0, inventory=None, description='', explored=0,
                 world=None):
        area = patrol_route[0]

        super().__init__(name, area, health, resilience, stealth, firearms, cover, hand_to_hand, hacking, observation,
                         acrobatics,
                         inventory, description, explored, world=world)

        self.alarm_level = 0.0
        self.init_observation = observation
        self.init_hand_to_hand = hand_to_hand
        self.max_observation = max_observation
        self.max_hand_to_hand = max_hand_to_hand

        self.alarm_increased_this_turn = False

        # Create a pendulum patrol route
        self.patrol_route = patrol_route + list(reversed(patrol_route))[1:-1]

        self.current_patrol_index = 0  # Current position in the patrol route
        self.is_patrolling = True

    def update_alarm_level(self, delta):

        logger.debug(f"Updating alarm level for {self.name}: {self.alarm_level} + {delta}")
        logger.debug(f"Pre-update skills: {self.skills}")

        if self.alarm_level == 1:
            return  # Don't update alarm level in fight mode

        if delta > 0:
            self.alarm_increased_this_turn = True

        # clamp between 0 and 1
        self.alarm_level = min(max(0, self.alarm_level + delta), 1)

        logger.debug(f"New alarm level: {self.alarm_level}")
        logger.debug(f"Post-update skills: {self.skills}")

    def update_skills(self):
        obs_inc = get_corresponding_value(self.alarm_level, OBS_THRESHS)
        self.skills['observation'] = self.init_observation + obs_inc
        self.skills['hand_to_hand'] = self.init_hand_to_hand + obs_inc

        # clamp skills between 0 and self.max_observation:
        self.skills['observation'] = min(max(0., self.skills['observation']), self.max_observation)
        self.skills['hand_to_hand'] = min(max(0., self.skills['hand_to_hand']), self.max_hand_to_hand)

    def advance_patrol_index(self):
        self.current_patrol_index += 1
        if self.current_patrol_index == len(self.patrol_route):
            self.current_patrol_index = 0


# Objective base class
class Objective(Entity):
    def __init__(self, name, area, description, difficulty, required_skill, explored=1,
                 world=None):
        super().__init__(name, area, description, explored=explored, world=world)
        self.difficulty = max(0, min(difficulty, 1))
        self.is_captured = False
        self.required_skill = required_skill

    def capture(self):
        self.is_captured = True
        self.name = f"{self.name} (Captured)"


class SimpleObjective(Objective):
    def __init__(self, name, area, description, difficulty, explored, world=None):
        super().__init__(name, area, description, difficulty, None, explored, world=world)

    def capture(self):
        self.is_captured = True
        return True


# Subclasses for specific objective types
class ComputerObjective(Objective):
    def __init__(self, name, area, description, difficulty, explored, world=None):
        super().__init__(name, area, description, difficulty, "hacking", explored, world=world)


class PersonObjective(Objective):
    def __init__(self, name, area, description, difficulty, explored, world=None):
        super().__init__(name, area, description, difficulty, "hand_to_hand", explored, world=world)


class OtherObjective(Objective):
    def __init__(self, name, area, difficulty, description, explored, world=None):
        super().__init__(name, area, description, difficulty, "observation", explored, world=world)


class Body(Entity):
    def __init__(self, name, area, description, world=None):
        super().__init__(name, area, description, world=world)


# Obstacle class
class Obstacle(Entity):
    def __init__(self, name, area, obstacle_type, difficulty, description, world=None):
        super().__init__(name, area, description, world=world)
        self.obstacle_type = obstacle_type
        self.difficulty = max(0, min(difficulty, 1))


class Equipment:
    def __init__(self, modifiers):
        self.modifiers = modifiers

    def __getitem__(self, key):
        return self.modifiers.get(key, 0)

    def __str__(self):
        # class name
        return f'{self.__class__.__name__}'


class Weapon(Equipment):
    pass


# Now a class for a submachine gun


class SubmachineGun(Weapon):

    def __init(self):
        modifiers = {
            'firearms': .2,
            'acrobatics': -.2,
            'stealth': -.2,
        }
        super().__init__(modifiers=modifiers)


class SniperRifle(Weapon):

    def __init__(self):
        modifiers = {
            'acrobatics': -.3,
            'stealth': -.4,
        }
        super().__init__(modifiers=modifiers)


class Connection:
    def __init__(self, area1, area2, description1='', description2='', sight_only=False,
                 spot_difficulty1=DEFAULT_SPOT_DIFFICULTY,
                 spot_difficulty2=DEFAULT_SPOT_DIFFICULTY,
                 investigate_difficulty1=0., investigate_difficulty2=0., access_difficulty1=0., access_difficulty2=0.,
                 is_locked1=False,
                 is_locked2=False,
                 noise_factor=.5, conn_type='door'):

        logger.debug(f"=== CREATING CONNECTION between {area1.name} and {area2.name} ===")
        logger.debug(f"Type: {conn_type}")
        logger.debug(f"Description 1->2: {description1}")
        logger.debug(f"Description 2->1: {description2}")
        logger.debug(f"Sight only: {sight_only}")
        logger.debug(f"Spot difficulties: 1->2={spot_difficulty1}, 2->1={spot_difficulty2}")
        logger.debug(f"Investigation difficulties: 1->2={investigate_difficulty1}, 2->1={investigate_difficulty2}")
        logger.debug(f"Access difficulties: 1->2={access_difficulty1}, 2->1={access_difficulty2}")
        logger.debug(f"Locks: 1->2={is_locked1}, 2->1={is_locked2}")
        logger.debug(f"Noise factor: {noise_factor}")

        self.area1 = area1
        self.area2 = area2
        self.description1 = description1  # Description from area1 to area2
        self.description2 = description2  # Description from area2 to area1
        self.sight_only = sight_only
        self.spot_difficulty1 = spot_difficulty1
        self.spot_difficulty2 = spot_difficulty2
        self.investigate_difficulty1 = investigate_difficulty1
        self.investigate_difficulty2 = investigate_difficulty2
        self.access_difficulty1 = access_difficulty1
        self.access_difficulty2 = access_difficulty2
        self.is_locked1 = is_locked1
        self.is_locked2 = is_locked2
        self.noise_factor = noise_factor

        assert conn_type in ['open', 'door', 'window']
        self.conn_type = conn_type

    def get_description(self, current_area):
        """Return the description of the connection from the perspective of the given area."""
        if current_area == self.area1:
            return self.description1
        elif current_area == self.area2:
            return self.description2
        else:
            raise ValueError("The provided area is not part of this connection.")

    def get_other_area(self, current_area):
        """Return the area on the other side of the connection from the given area."""
        if current_area == self.area1:
            return self.area2
        elif current_area == self.area2:
            return self.area1
        else:
            raise ValueError("The provided area is not part of this connection.")

    def get_spot_difficulty(self, current_area):
        """Return the spot difficulty from the perspective of the given area."""
        if current_area == self.area1:
            return self.spot_difficulty1
        elif current_area == self.area2:
            return self.spot_difficulty2
        else:
            raise ValueError("The provided area is not part of this connection.")

    def get_investigate_difficulty(self, current_area):
        """Return the investigate difficulty from the perspective of the given area."""
        if current_area == self.area1:
            return self.investigate_difficulty1
        elif current_area == self.area2:
            return self.investigate_difficulty2
        else:
            raise ValueError("The provided area is not part of this connection.")

    def get_access_difficulty(self, current_area):
        """Return the access difficulty from the perspective of the given area."""
        if current_area == self.area1:
            return self.access_difficulty1
        elif current_area == self.area2:
            return self.access_difficulty2
        else:
            raise ValueError("The provided area is not part of this connection.")

    def is_locked(self, current_area):
        """Return whether the other area is locked from the perspective of the given area."""
        if current_area == self.area1:
            return self.is_locked1
        elif current_area == self.area2:
            return self.is_locked2
        else:
            raise ValueError("The provided area is not part of this connection.")

    def unlock(self):
        self.is_locked1 = False
        self.is_locked2 = False

    def get_peek_difficulty(self, area):
        raise NotImplementedError


class Area(Entity):
    def __init__(self, name, description, x, y, width, height, color, image=None,
                 hiding_modifier=0, cover_modifier=0,
                 noise_baseline=0, explored=0, world=None, is_extraction_point=False):

        logger.debug(f"=== CREATING AREA: {name} ===")
        logger.debug(f"Description: {description}")
        logger.debug(f"Position: x={x}, y={y}, width={width}, height={height}")
        logger.debug(f"Modifiers: hiding={hiding_modifier}, cover={cover_modifier}")
        logger.debug(f"Noise baseline: {noise_baseline}")
        logger.debug(f"Initial exploration: {explored}")
        logger.debug(f"Is extraction point: {is_extraction_point}")

        # Update description to include hiding bonus and cover bonus

        super().__init__(name, area=None, description=description, explored=explored, world=world)
        self.hiding_modifier = hiding_modifier
        self.cover_modifier = cover_modifier
        self.noise_baseline = noise_baseline
        self.connections = []  # List of Connection objects
        self.entities = []  # List of entities currently in this area
        self.is_extraction_point = is_extraction_point  # Boolean indicating if this area is an extraction point

        self.noise_level = noise_baseline  # above baseline. meaning noticeable
        self.noise_duration = 0
        self.chase_pointer = None  # Points to another area where the last non-hidden agent in a room moved to

        # For the map renderring
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.color = color
        self.image = image

    def connect(self, other_area, description1='', description2='', sight_only=False, spot_difficulty1=0,
                spot_difficulty2=0, investigate_difficulty1=0,
                investigate_difficulty2=0, access_difficulty1=0, access_difficulty2=0, is_locked1=False,
                is_locked2=False,
                noise_factor=.5):
        """Connect this area to another area with specific connection attributes."""
        # Check if a connection already exists to prevent duplicate connections
        if not any(conn.area1 == other_area or conn.area2 == other_area for conn in self.connections):
            connection = Connection(self, other_area, description1, description2, sight_only, spot_difficulty1,
                                    spot_difficulty2,
                                    investigate_difficulty1, investigate_difficulty2, access_difficulty1,
                                    access_difficulty2, is_locked1, is_locked2, noise_factor)
            # Add the same Connection object to both areas to represent the bidirectional connection
            self.connections.append(connection)
            other_area.connections.append(connection)

    def connect_open(self, other_area, description1='', description2='', sight_only=False,
                     spot_difficulty1=DEFAULT_SPOT_DIFFICULTY,
                     spot_difficulty2=DEFAULT_SPOT_DIFFICULTY, investigate_difficulty1=0,
                     investigate_difficulty2=0, access_difficulty1=0, access_difficulty2=0, is_locked1=False,
                     is_locked2=False,
                     noise_factor=.75):
        """Connect this area to another area with specific connection attributes."""

        logger.debug(f"=== CONNECTING AREAS with open connection ===")
        logger.debug(f"From: {self.name} To: {other_area.name}")
        logger.debug(f"Noise factor: {noise_factor}")
        logger.debug(f"Spot difficulties: {spot_difficulty1}, {spot_difficulty2}")

        # Check if a connection already exists to prevent duplicate connections
        if not any(conn.area1 == other_area or conn.area2 == other_area for conn in self.connections):
            connection = Connection(self, other_area, description1, description2, sight_only, spot_difficulty1,
                                    spot_difficulty2,
                                    investigate_difficulty1, investigate_difficulty2, access_difficulty1,
                                    access_difficulty2, is_locked1, is_locked2, noise_factor, conn_type='open')
            # Add the same Connection object to both areas to represent the bidirectional connection
            self.connections.append(connection)
            other_area.connections.append(connection)

    def connect_door(self, other_area, description1='', description2='', sight_only=False,
                     spot_difficulty1=DEFAULT_SPOT_DIFFICULTY,
                     spot_difficulty2=DEFAULT_SPOT_DIFFICULTY, investigate_difficulty1=0,
                     investigate_difficulty2=0, access_difficulty1=0, access_difficulty2=0, is_locked1=False,
                     is_locked2=False,
                     noise_factor=.5):
        """Connect this area to another area with specific connection attributes."""

        logger.debug(f"=== CONNECTING AREAS with door ===")
        logger.debug(f"From: {self.name} To: {other_area.name}")
        logger.debug(f"Noise factor: {noise_factor}")
        logger.debug(f"Spot difficulties: {spot_difficulty1}, {spot_difficulty2}")

        # Check if a connection already exists to prevent duplicate connections
        if not any(conn.area1 == other_area or conn.area2 == other_area for conn in self.connections):
            connection = Connection(self, other_area, description1, description2, sight_only, spot_difficulty1,
                                    spot_difficulty2,
                                    investigate_difficulty1, investigate_difficulty2, access_difficulty1,
                                    access_difficulty2, is_locked1, is_locked2, noise_factor, conn_type='door')
            # Add the same Connection object to both areas to represent the bidirectional connection
            self.connections.append(connection)
            other_area.connections.append(connection)

    def connect_window(self, other_area, description1='', description2='', sight_only=False,
                       spot_difficulty1=DEFAULT_SPOT_DIFFICULTY,
                       spot_difficulty2=DEFAULT_SPOT_DIFFICULTY, investigate_difficulty1=0,
                       investigate_difficulty2=0, access_difficulty1=.1, access_difficulty2=.1, is_locked1=False,
                       is_locked2=False,
                       noise_factor=.5):

        logger.debug(f"=== CONNECTING AREAS with window ===")
        logger.debug(f"From: {self.name} To: {other_area.name}")
        logger.debug(f"Noise factor: {noise_factor}")
        logger.debug(f"Spot difficulties: {spot_difficulty1}, {spot_difficulty2}")

        """Connect this area to another area with specific connection attributes."""
        # Check if a connection already exists to prevent duplicate connections
        if not any(conn.area1 == other_area or conn.area2 == other_area for conn in self.connections):
            connection = Connection(self, other_area, description1, description2, sight_only, spot_difficulty1,
                                    spot_difficulty2,
                                    investigate_difficulty1, investigate_difficulty2, access_difficulty1,
                                    access_difficulty2, is_locked1, is_locked2, noise_factor, conn_type='window')
            # Add the same Connection object to both areas to represent the bidirectional connection
            self.connections.append(connection)
            other_area.connections.append(connection)

    def is_accessible(self, other_area):
        return self.get_connection_info(other_area) is not None

    def describe_passage(self, other_area):
        if self.is_accessible(other_area):
            return self.get_connection_info(other_area).get_description(self)

    def is_passage_locked(self, other_area):
        if self.is_accessible(other_area):
            return self.get_connection_info(other_area).is_locked(self)

    def is_passage_sight_only(self, other_area):
        if self.is_accessible(other_area):
            return self.get_connection_info(other_area).sight_only

    def get_passage_spot_difficulty(self, other_area):
        if self.is_accessible(other_area):
            return self.get_connection_info(other_area).get_spot_difficulty(self)

    def get_passage_investigate_difficulty(self, other_area):
        if self.is_accessible(other_area):
            return self.get_connection_info(other_area).get_investigate_difficulty(self)

    def get_passage_access_difficulty(self, other_area):
        if self.is_accessible(other_area):
            return self.get_connection_info(other_area).get_access_difficulty(self)

    def get_connected_areas(self):
        """Return a list of areas connected to this area."""
        return [conn.get_other_area(self) for conn in self.connections]

    def get_connection_info(self, other_area):
        """Retrieve connection information between this area and another area."""
        for connection in self.connections:
            if connection.get_other_area(self) == other_area:
                return connection
        return None  # Return None if no connection is found

    def __str__(self):
        connected_areas = []
        for conn in self.connections:
            other_area = conn.get_other_area(self)
            # Add the name of the other area
            connected_area_str = other_area.name
            # If the other area is explored, add the connection description in parentheses
            if other_area.get_explored() > 0:
                description = conn.get_description(self)
                if description:
                    connected_area_str += f" ({description})"
            connected_areas.append(connected_area_str)

        connected_areas_str = ', '.join(connected_areas)
        return f"{self.name}:\n{self.description}\nEntities: {', '.join(str(entity) for entity in self.entities)}\nConnected areas: {connected_areas_str}"


class MissionLog(List):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.print_queue = deque()
        self.last_command = None

    def append(self, item, print_it=True, push_to_queue=True, is_command=False):

        item = item.replace(' (Captured)', '')

        if print_it:
            print(item)
        if push_to_queue:
            self.print_queue.append(item)
        if is_command:
            self.last_command = item

        super().append(item)



class GameController:
    def __init__(self, world, game_map, mode='auto', agents_hidden=False, hostiles_visible=False):

        mode_map = {
            'a': 'auto',
            'sa': 'semi-auto',
            'm': 'manual',
            't': 'test'
        }
        mode = mode_map.get(mode, mode)

        assert mode in ['auto', 'semi-auto', 'manual', 'test']

        self.world = world
        self.game_map = game_map
        self.mode = mode
        self.agents_hidden = agents_hidden
        self.hostiles_visible = hostiles_visible

        self.turn_count = 0
        self.mission_log = MissionLog()
        open('logs_internal/decision_prompts.txt', 'w').close()

        self.turn_counter = 0

        # Populate Areas with Entities
        for entity in self.get_entities(Character) + self.get_entities(Objective):
            entity.area.entities.append(entity)

        for agent in self.get_entities(Agent):
            for connection in agent.area.connections:
                if agent.take_action('look_around', connection):
                    connection.get_other_area(agent.area).set_explored(1)

            for entity in agent.area.entities:

                # This assumes objectives are stationary
                if isinstance(entity, Objective):
                    entity.set_explored(2)
                else:
                    entity.set_explored(1)

    def game_loop(self):

        for entity_id, entity in self.world.entity_registry.items():
            if isinstance(entity, Agent) and not isinstance(entity, Hostile) and entity.health > 0:
                for area in entity.area.get_connected_areas():
                    area.set_explored(1)

        cont = True
        while cont:

            # inp = inputt('> ', 2)
            inp = input('> ')

            if inp in ['/q', '/quit', '/exit', 'quit()']:
                break
            elif inp in ['/m', '/map']:
                self.game_map.draw_partial_graph()
            elif inp in ['/fm', '/fullmap']:
                self.game_map.draw_graph()
            else:
                # Add this line:
                if inp:
                    self.mission_log.append(f"Mission Control: {inp}", print_it=False)
                cont = self.process_turn()

        print("\nMission Ended")

    def process_turn(self):
        """Process a turn."""
        # Initialize character statuses
        agents = [agent for agent in self.get_entities(Agent) if agent.health > 0]

        for agent in agents:
            agent.knowledge_base = self.describe_knowledge_base(agent)
            if self.agents_hidden:
                agent.is_hidden = True

        # Reset
        for hostile in self.get_entities(Hostile):
            hostile.alarm_increased_this_turn = False
            hostile.is_peeked = False

        if not agents:
            return False

        decide_prompts = [agent.make_decision_prompt() for agent in agents]

        for agent, decide_prompt in zip(agents, decide_prompts):
            with open('logs_internal/decision_prompts.txt', 'a') as f:
                f.write(
                    f"{agent.name}:\n--------------------------\n\n {decide_prompt}\n\n==========================\n\n")

        agent2decision = {}
        if self.mode == 'auto':
            # Production mode decision making:
            # Uncomment this line for the actual AI system to make decisions
            # This requires defining the AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT environment variables

            remaining_to_execute = decide_prompts.copy()
            agents_to_execute = agents.copy()
            i = 0

            while remaining_to_execute:

                if i >= 5:
                    raise Exception('Not supposed to fail evaluating all prompt outputs 5 times in a row')

                decisions = query_lbgpt('', remaining_to_execute)

                # Validate
                for i, decision in enumerate(decisions):

                    try:

                        agent = agents_to_execute[i]
                        evaled_decision = response_parsing(decision)
                        action_argument_dict = agent.generate_action_arguments()
                        action = evaled_decision['action']

                        for arg in evaled_decision['arguments']:
                            print('>>>', arg, type(arg))

                        try:
                            args = [UUID(arg) for arg in evaled_decision['arguments']]
                        except ValueError:
                            print(f"Invalid UUID format for agent {agent.name}, retrying...")
                            continue

                        assert action in action_argument_dict, f"Invalid action: {action}. Valid actions: {list(action_argument_dict.keys())}"
                        valid_args = [aarg['id'] for aarg in action_argument_dict.get(action, [])]
                        assert all(
                            arg in valid_args for arg in
                            args), f"Invalid arguments: {args}. Valid arguments: {valid_args}"

                        agent2decision[agent] = evaled_decision

                    except AssertionError as e:
                        print(f"Error processing decision {i}: {str(e)}")

                remaining_to_execute = [
                    remaining_to_execute[j] for j in range(len(remaining_to_execute)) if
                    agents_to_execute[j] not in agent2decision
                ]
                agents_to_execute = [
                    agent for agent in agents_to_execute if agent not in agent2decision
                ]
                i += 1

        elif self.mode == 'manual':

            for agent in agents:

                action_arguments = agent.generate_action_arguments()
                prompt = agent.make_manual_decision_prompt()

                # Display it to the user so they can make a choice for this agent
                print(prompt)

                arguments = []
                while True:
                    try:
                        actionarg = input(f"{agent.name} action: ")
                        actionarg = actionarg.split(' ')
                        assert actionarg

                        if len(actionarg) == 1:
                            action = actionarg[0]
                        else:
                            action = actionarg[0]
                            arguments = [action_arguments[action][int(arg.strip())]['id'] for arg in actionarg[1:]]

                        assert action in action_arguments.keys()
                        break
                    except AssertionError:
                        print(
                            f"Invalid input. Please enter one of the valid actions: {', '.join(list(action_arguments.keys()))}.")

                if arguments:
                    pass
                elif not action_arguments[action]:
                    arguments = []
                elif len(action_arguments[action]) == 1:
                    arguments = [action_arguments[action][0]['id']]
                else:

                    while True:
                        argument = input(f"Choose arg: ")
                        try:
                            argument = int(argument.strip())
                            assert argument < len(action_arguments[action])
                            break
                        except (AssertionError, ValueError):
                            print(
                                f"Invalid input. Please enter an index up to {len(action_arguments[action]) - 1}.")

                    arguments = [str(action_arguments[action][argument]['id'])]

                decision = {'action': action, 'arguments': arguments}
                agent2decision[agent] = decision

        elif self.mode == 'test':
            # Test mode decision making:
            # This is an example of how to hardcode a decision logic for testing
            # You can change it as needed, depending on the scenario you want to test

            for agent in agents:
                if self.turn_counter > 100:
                    decision = "{'action': 'investigate', 'arguments': []}"  # for debugging
                else:
                    decision = "{'action': 'wait', 'arguments': []}"  # for debugging

                agent2decision[agent] = decision

        else:
            raise Exception('Invalid mode')

        decisions_dict = {
            agent.name: {
                'action': decision['action'],
                'arguments': [str(arg) for arg in decision['arguments']],  # Convert UUIDs to strings
                'reasoning': decision.get('reasoning', '')
            }
            for agent, decision in agent2decision.items()
        }
        logger.debug(f"Decisions: {json.dumps(decisions_dict, indent=2)}")

        for i, (agent, decision) in enumerate(agent2decision.items()):
            agent = agents[i]
            area = agent.area

            # print('Reasoning:', decision['reasoning'])
            # print('Arguments:', [arg for arg in decision['arguments']])

            # Get the action and args from the decision
            action = decision['action']

            # This step makes sure that the arguments are still in the game.
            # For example if 2 agents shoot 1 target, and it goes down after one shot,
            # then when the second agent's decision to shoot is queued, the target will no longer exist
            if all(UUID(str(arg)) in self.world.entity_registry for arg in decision['arguments']):

                args = [self.world.entity_registry[UUID(str(arg))] for arg in decision['arguments']]
                func = getattr(self, action)  # Pick function based on action
                func(agent, *args)  # Apply the function to the args

            # Calculate the base alarm increase
            skill = ACTION_TO_SKILL[action]
            base_alarm_increase = get_alarm_increase(action, agent.skills[skill])

            # Peeking alarm depends on connection type
            # TODO: generalize this and wrap in an appropriate function
            if action == 'peek':
                conn = agent.area.get_connection_info(args[0])
                if conn.conn_type == 'door':
                    base_alarm_increase += PEEK_ALARM_PENALTY

            logging.debug(f"Action: {action} | Base alarm increase: {base_alarm_increase}")

            # Update alarms for the current area
            self.update_alarm_levels(area, base_alarm_increase)

            # If the agent moved to a new area, update alarms there as well
            if area != agent.area:
                self.update_alarm_levels(agent.area, base_alarm_increase)

        # Hostile actions
        for hostile in self.get_entities(Hostile):

            area = hostile.area

            # If there are agents in the area with not is_hidden:
            potential_targets = [agent for agent in self.get_entities(Agent, area) if not agent.is_hidden]
            if potential_targets:

                target = random.choice(potential_targets)

                self.shoot(hostile, target)

                # Update alarms for the current area
                self.update_alarm_levels(area, 2)

            else:

                self.move_hostile(hostile)

                if not hostile.alarm_increased_this_turn:
                    hostile.update_alarm_level(RELAX_DEC)

            hostile.update_skills()

        # For each agent, print location and is_hidden:
        for agent in self.get_entities(Agent):
            logger.debug(f"{agent.name} is at {agent.area.name} and is_hidden: {agent.is_hidden}")
        for hostile in self.get_entities(Hostile):
            logger.debug(
                f"{hostile.name}: at {hostile.area.name}, alarm level: {hostile.alarm_level:.3f} obs: {hostile.skills['observation']:.3f}, h2h: {hostile.skills['hand_to_hand']:.3f}, alarm_increased_this_turn: {hostile.alarm_increased_this_turn}, health: {hostile.health:.2f}")

        # Reset area values
        for area in self.get_entities(Area):
            area.noise_level = area.noise_baseline
            area.chase_pointer = None

        self.turn_counter += 1
        return True

    def update_alarm_levels(self, area, base_alarm_increase):
        """
        Update the alarm levels for hostiles in the given area and its connected areas
        based on the base alarm increase and noise propagation factors.
        """

        area.noise_level += base_alarm_increase
        # logger.debug(f"Changed noise level for area: {area.name} to {area.noise_level:.2f}")

        # Update alarms for hostiles in the given area
        for hostile in self.get_entities(Hostile, area):
            hostile.update_alarm_level(base_alarm_increase)

        # Propagate alarms to connected areas
        for connection in area.connections:
            other_area = connection.get_other_area(area)

            propagation = base_alarm_increase * connection.noise_factor
            other_area.noise_level += propagation
            # logger.debug(f"Changed noise level for area: {other_area.name} to {other_area.noise_level:.2f}")
            for hostile in self.get_entities(Hostile, other_area):
                hostile.update_alarm_level(propagation)

    def move_hostile(self, hostile):
        """
        Move the hostile along their patrol route, allowing for alarm interruptions and resuming patrols correctly.
        """
        logger.debug(
            f"Hostile: {hostile.name} | Current Area: {hostile.area.name} | Alarm Level: {hostile.alarm_level:.2f}")

        route = hostile.patrol_route
        n = len(route)

        if n <= 1:
            logger.debug("Patrol route is too short or undefined. Staying in the current area.")
            return

        # TODO: test this
        if hostile.area.chase_pointer is not None:
            target_area = hostile.area.chase_pointer

        elif hostile.alarm_level > 0.5:
            hostile.is_patrolling = False

            # Identify the area with the highest noise level
            areas_with_noise = [(hostile.area, hostile.area.noise_level)] + [
                (connection.get_other_area(hostile.area), connection.get_other_area(hostile.area).noise_level)
                for connection in hostile.area.connections
            ]

            areas_with_noise.sort(key=lambda x: x[1], reverse=True)  # Sort by noise level descending

            # If there's no noise anywhere, move randomly
            if areas_with_noise[0][1] == 0:
                connected_areas = hostile.area.get_connected_areas()
                target_area = random.choice(connected_areas)
                logger.debug(f"No noise detected. Moving randomly to {target_area.name}")
            else:
                target_area = areas_with_noise[0][0]
                logger.debug(f"Moving to the area with the highest noise: {target_area.name}")

        else:
            hostile.is_patrolling = True

            if random.random() < GUARD_STAY_PROB:
                return

            # Determine the next area in the patrol route
            if hostile.area == route[hostile.current_patrol_index]:
                # Update the patrol index only if the hostile is at the current patrol area
                hostile.advance_patrol_index()

            target_area = route[hostile.current_patrol_index]
            logger.debug(f"Resuming patrol: Next target area is {target_area.name}")

        # Determine the next step toward the target area
        if target_area in hostile.area.get_connected_areas():
            next_area = target_area
            logger.debug(f"Target area is adjacent: Moving to {next_area.name}")
        else:
            try:
                shortest_path = self.game_map.get_shortest_path(hostile.area, target_area)
                logger.debug(f"Shortest path: {[area.name for area in shortest_path]}")
                next_area = shortest_path[min(1, len(shortest_path) - 1)]  # The first step toward the target area

                logger.debug(f"Target area is not adjacent: Taking step toward {next_area.name} via shortest path")
            except nx.NetworkXNoPath:
                logger.debug("No path exists to the target area. Staying in the current area.")
                return

        # Move the hostile to the next area
        self.change_area(hostile, next_area)

    def get_entities(self, class_, area=None):

        if area is None:
            return [entity for entity in self.world.entity_registry.values() if isinstance(entity, class_)]
        else:
            return [entity for entity in area.entities if isinstance(entity, class_)]

    def change_area(self, entity, new_area):
        old_area = entity.area

        if old_area == new_area:
            return False

        logger.debug(f"Moving Entity: {entity.name} | From: {old_area.name} | To: {entity.name}")

        assert new_area in [conn.get_other_area(old_area) for conn in
                            old_area.connections], "Entity is not connected to the new area."

        old_area.entities.remove(entity)
        new_area.entities.append(entity)
        entity.area = new_area

        if self.get_entities(Hostile, old_area) and \
                hasattr(entity, 'is_hidden') and \
                not entity.is_hidden and \
                not [agent for agent in self.get_entities(Agent, old_area) if not agent.is_hidden]:
            old_area.chase_pointer = new_area

        return True

    def report(self, agent):
        pass

    def answer_question(self, agent, question):
        pass

    def wait(self, agent):
        self.mission_log.append(f"{agent.name}: Waiting in {agent.area.name}.")
        success = agent.take_action('wait')
        return success

    def move(self, agent, target_area):
        """
        Move the agent to the target area, marking the area and its objects as explored.
        """
        if target_area in agent.area.get_connected_areas():
            self.mission_log.append(f"{agent.name}: Moving to {target_area.name}.")

            area = agent.area
            if area.is_passage_locked(target_area):
                self.mission_log.append(f"{agent.name}: Locked.")
                return False

            access_difficulty = area.get_passage_access_difficulty(target_area)

            if access_difficulty:
                base_alarm_increase = get_alarm_increase("bypass", agent.skills["acrobatics"])
                logging.debug(f"Bypass alarm increase: {base_alarm_increase:.2f}")

                # Update alarms for the current area
                self.update_alarm_levels(area, base_alarm_increase)

                result = agent.take_action('bypass', modifier=access_difficulty)
                if not result:
                    return False

            # Update the current area and the target area's entities list
            self.change_area(agent, target_area)
            agent.is_hidden = False

            # Mark the area and objects as explored
            target_area.set_explored(1)
            for entity in target_area.entities:

                if agent.take_action('look_around', entity):

                    # This assumes Objectives are stationary
                    if isinstance(entity, Objective):
                        entity.set_explored(2)
                    else:
                        entity.set_explored(1)

            for connection in target_area.connections:
                if agent.take_action('look_around', connection):
                    connection.get_other_area(agent.area).set_explored(1)

            area.get_connection_info(target_area).unlock()

            return True
        else:
            raise ConnectionError(
                f"{agent.name} attempting to move to {target_area.name}, but {target_area.name} is not connected to {agent.name}'s current area: {agent.area.name}.")

    def peek(self, agent, area):
        assert area in agent.area.get_connected_areas(), f"Can only peek into adjacent area"
        detectities = [entity for entity in area.entities if
                       (not isinstance(entity, Agent)) and
                       agent.take_action('peek', entity)]

        self.mission_log.append(f"{agent.name}: Peeked into {area.name}.")
        for entity in detectities:

            # This assumes objectives are stationary
            if isinstance(entity, Objective):
                entity.set_explored(2)
            else:
                entity.set_explored(1)

            entity.is_peeked = True

    def investigate(self, agent):

        area = agent.area

        self.mission_log.append(f"{agent.name}: Investigating {area.name}.")
        detectities = [entity for entity in area.entities if
                       (not isinstance(entity, Agent)) and
                       agent.take_action('investigate', entity)]

        for connection in area.connections:
            if agent.take_action('investigate', connection):
                detectities.append(connection.get_other_area(area))

        for entity in detectities:
            # This assumes objectives are stationary
            if isinstance(entity, Objective):
                entity.set_explored(2)
            else:
                entity.set_explored(1)

    def hide(self, agent):
        area = agent.area
        hostile_values = [agent.take_action('hide', hostile, modifier=area.hiding_modifier) for hostile in
                          self.get_entities(Hostile, area)]
        result = all(hostile_values)

        agent.is_hidden = result if not self.agents_hidden else True

        self.mission_log.append(
            f"{agent.name}: {f'Secure in {agent.area.name}.' if result else f'Cover blown in {agent.area.name}!'}")
        return result

    def take_out(self, agent, hostile):
        assert agent.area is hostile.area, (f"Agent {agent.name} and hostile {hostile.name} must be in the same area "
                                            f"to attempt take out.")

        self.hide(agent)

        result = agent.take_action('take_out', hostile)

        if result:
            # Create body
            self.world.remove_entity(hostile)

        self.mission_log.append(
            f"{agent.name}: {f'{hostile.name} taken out' if result else f'In melee with {hostile.name}'}!")
        return result

    def shoot(self, shooter, target):
        """
        Handles shooting action between two characters. Returns 2 if target killed, 1 if hit, 0 if miss.

        Debug info shows all key values and state changes during the shooting process.
        """
        logger.debug(f"=== SHOOTING SEQUENCE START ===")
        logger.debug(f"Shooter: {shooter.name} ({type(shooter).__name__})")
        logger.debug(f"Target: {target.name} ({type(target).__name__})")
        logger.debug(f"Initial states:")
        logger.debug(f"  Shooter health: {shooter.health:.2f}")
        logger.debug(f"  Shooter firearms skill: {shooter.skills['firearms']:.2f}")
        logger.debug(f"  Shooter hidden: {shooter.is_hidden}")
        logger.debug(f"  Target health: {target.health:.2f}")
        logger.debug(f"  Target cover skill: {target.skills['cover']:.2f}")
        logger.debug(f"  Area cover modifier: {shooter.area.cover_modifier:.2f}")

        # Validate shooter and target are in same area
        assert shooter.area is target.area, (
            f"Shooter {shooter.name} in {shooter.area.name} "
            f"cannot shoot target {target.name} in {target.area.name}"
        )

        # Shooting reveals position
        shooter.is_hidden = False
        logger.debug(f"Shooter revealed position: hidden = {shooter.is_hidden}")

        area = shooter.area

        # Determine if shot hits
        hit = shooter.take_action('shoot', target)
        logger.debug(f"Shot hit check result: {hit}")

        # Calculate damage
        if hit:
            # Roll shooter effectiveness
            shooter_res = random.gauss(
                shooter.skills['firearms'],
                SKILL_SIGMA
            )
            logger.debug(f"Shooter effectiveness roll: {shooter_res:.3f}")

            # Roll target defense
            total_cover = target.skills['cover'] + area.cover_modifier
            target_res = random.gauss(total_cover, SKILL_SIGMA)
            logger.debug(f"Target defense roll: {target_res:.3f}")
            logger.debug(f"  From: cover skill ({target.skills['cover']:.2f}) + "
                         f"area modifier ({area.cover_modifier:.2f})")

            # Calculate final damage
            damage = max(0., min(.1, shooter_res - target_res))
            logger.debug(f"Calculated damage: {damage:.3f}")
        else:
            damage = 0
            logger.debug("Shot missed - no damage")

        # Log the shooting event
        if isinstance(shooter, Agent):
            self.mission_log.append(f"{shooter.name}: Opened fire at {target.name}!")
        if isinstance(target, Agent):
            if damage > 0:
                self.mission_log.append(f"{target.name}: I'm hit!")
            else:
                self.mission_log.append(f"{target.name}: Under fire!")

        # Apply damage and check for death
        old_health = target.health
        target.health -= damage
        logger.debug(f"Target health: {old_health:.2f} -> {target.health:.2f}")

        if target.health <= 0:
            logger.debug(f"Target {target.name} killed")
            if isinstance(shooter, Agent):
                self.mission_log.append(f"{shooter.name}: Target down!")
            elif isinstance(target, Agent):
                self.mission_log.append(f"Mission Control: Agent Down!")
            self.world.remove_entity(target)
            logger.debug("=== SHOOTING SEQUENCE END (TARGET KILLED) ===")
            return 2

        logger.debug(f"=== SHOOTING SEQUENCE END (DAMAGE: {damage:.3f}) ===")
        return damage > 0

    def silent_shoot(self, shooter, target):
        raise NotImplementedError("Silent shooting not implemented yet.")

    def capture(self, agent, target):
        assert agent.area is target.area, f"Agent {agent.name} and target {target.name} must be in the same area to attempt capture."
        result = agent.take_action('capture', target)
        if result:
            target.capture()

        self.mission_log.append(f"{agent.name}: {target.name} {'captured' if result else 'failed to capture'}!")
        return result

    def bypass(self, agent, obstacle):
        assert agent.area is obstacle.area, f"Agent {agent.name} and obstacle {obstacle.name} must be in the same area to attempt bypass."
        result = agent.take_action('bypass', obstacle)
        self.mission_log.append(
            f"{agent.name}: {f'{obstacle.name} cleared' if result else f'path blocked by {obstacle.name}'}!")
        return result

    def sneak(self, agent, area):

        # Hide in current room (even if already hidden, moving requires another hiding attempt)
        hide_result1 = self.hide(agent)

        self.move(agent, area)

        # Hide in new room
        hide_result2 = self.hide(agent)

        return hide_result2

    def charge(self, agent, area):
        """
        No hostiles found: returns None
        """
        self.move(agent, area)
        hostiles = [entity for entity in area.entities if isinstance(entity, Hostile)]
        if hostiles:
            shoot_result = self.shoot(agent, random.choice(hostiles))
            return shoot_result

    def exfiltrate(self, agent):
        self.world.remove_entity(agent)
        self.mission_log.append(f"{agent.name}: Exfiltrated!")

    def describe_knowledge_base(self, agent):
        """
        Create a verbal description of all explored entities, their locations if known,
        and connections between areas if known. It returns a list of descriptive statements in a structured format.

        Suggested Structure:
        - Areas
        - Agents
        - Hostiles
        - Objectives
        - Hiding Places

        The generated descriptions are intended for prompt use.
        """
        descriptions = []

        # Separate sections for each type of entity
        area_descriptions = []
        agent_descriptions = []
        hostile_descriptions = []
        objective_descriptions = []

        # Iterate over all areas to generate descriptions
        for area in self.game_map.areas:
            if area.get_explored() > 0:
                area_description = {
                    "ID": area.id,
                    "Name": area.name,
                    "Description": area.description,
                    "Connections": []
                }
                # Add connected areas that have been explored
                for connection in area.connections:
                    if connection.get_other_area(area).get_explored():
                        connection_description = {
                            "Name": connection.get_other_area(area).name,
                            "ID": connection.get_other_area(area).id,
                            "Details": connection.get_description(area) or ""
                        }
                        area_description["Connections"].append(connection_description)
                area_descriptions.append(area_description)

        # Iterate over all entities to generate descriptions for non-area entities
        all_entities = list(self.world.entity_registry.values())
        for entity in all_entities:
            if not isinstance(entity, Area) and entity.get_explored() > 0:
                entity_data = {
                    "ID": entity.id,
                    "Name": entity.name,
                    "Description": entity.description,
                    "Location": {
                        "Name": entity.area.name,
                        "ID": entity.area.id
                    } if entity.area and entity.area.get_explored() and entity.get_explored() > 1 else None
                }
                # Categorize the entity into appropriate sections
                if isinstance(entity, Agent):
                    agent_descriptions.append(entity_data)
                elif isinstance(entity, Hostile):
                    hostile_descriptions.append(entity_data)
                elif isinstance(entity, Objective):
                    objective_descriptions.append(entity_data)
                else:
                    raise NotImplementedError(f"Unsupported entity type: {type(entity).__name__}")

        # Assemble all parts into structured format
        if area_descriptions:
            descriptions.append("Areas:")
            for area in area_descriptions:

                area_id = area["ID"]
                area_name = area["Name"]
                area_desc = area["Description"]
                connections = area["Connections"]

                description_str = f"  - ID: {area_id}\n    Name: {area_name}\n    Description: {area_desc}"
                if connections:
                    description_str += f"\n    Connections: {', '.join([conn['Name'] for conn in connections])}"

                descriptions.append(description_str)

        if agent_descriptions:
            descriptions.append("\nAgents:")
            for agent in agent_descriptions:
                description_str = f"  - ID: {agent['ID']}\n    Name: {agent['Name']}\n    Description: {agent['Description']}\n    Location: {agent['Location']['Name']} (ID: {agent['Location']['ID']})" if \
                    agent[
                        'Location'] else f"  - ID: {agent['ID']}\n    Name: {agent['Name']}\n    Description: {agent['Description']}"
                descriptions.append(description_str)

        if hostile_descriptions:
            descriptions.append("\nHostiles:")
            for hostile in hostile_descriptions:
                description_str = f"  - ID: {hostile['ID']}\n    Name: {hostile['Name']}\n    Description: {hostile['Description']}\n    Location: {hostile['Location']['Name']} (ID: {hostile['Location']['ID']})" if \
                    hostile[
                        'Location'] else f"  - ID: {hostile['ID']}\n    Name: {hostile['Name']}\n    Description: {hostile['Description']}"
                descriptions.append(description_str)

        if objective_descriptions:
            descriptions.append("\nObjectives:")
            for objective in objective_descriptions:
                description_str = f"  - ID: {objective['ID']}\n    Name: {objective['Name']}\n    Description: {objective['Description']}\n    Location: {objective['Location']['Name']} (ID: {objective['Location']['ID']})" if \
                    objective[
                        'Location'] else f"  - ID: {objective['ID']}\n    Name: {objective['Name']}\n    Description: {objective['Description']}"
                descriptions.append(description_str)

        # Append mission log
        description = '\n'.join(descriptions) + '\n\n-----------------\n\nMission Log:\n' + '\n'.join(
            self.mission_log[-100:]) + '\n\n-----------------'

        if self.mission_log.last_command is not None:
            description += f"Keep especially this instruction in mind when making your decision:\n\n Control: {self.mission_log.last_command}\n\n-----------------"

        return description
