from collections import defaultdict

def get_alarm_increase(action, skill_level):
    """
    Calculate the alarm increase based on the action and the agent's skill level.

    Args:
        action (str): The action being performed.
        skill_level (float): The skill level of the agent (1.0 for high skill, 0.7 for intermediate).

    Returns:
        float: The alarm increase caused by the action.
    """
    # Define the alarm level mapping
    alarm_values = {
        "wait": defaultdict(lambda: 0), # Temp val
        "look_around": {1.0: 0.0, 0.7: 0.0},
        "peek": {1.0: 0.02, 0.7: 0.05},
        "investigate": {.1: 0.0, 0.7: 0.1}, # Temp val
        "hide": {1.0: 0.15, 0.7: 0.2, .0: .5},
        "take_out": {1.0: 0.3, 0.7: 0.6},
        "shoot": defaultdict(lambda: 2),
        "bypass": {1.0: 0.2, 0.7: 0.5},
        "capture": {1.0: 0.4, 0.7: 0.7},
        "sneak" : {1.0: 0.15, 0.7: 0.2, .0: .5},
        "charge" : defaultdict(lambda: 1),
        "exfiltrate": {1.0: 0.15, 0.7: 0.2, .0: .5},
    }

    # Ensure the action is valid
    if action not in alarm_values:
        raise ValueError(f"Unknown action: {action}")

    # Ensure the skill level is valid
    if skill_level not in [1.0, 0.7, .0]:
        raise ValueError(f"Invalid skill level: {skill_level}. Must be 1.0 or 0.7.")

    # Return the corresponding alarm increase
    return alarm_values[action][skill_level]

