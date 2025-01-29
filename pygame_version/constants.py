
DEBUG_MODE = False

AREA_MOD_PROB = .05

PEEK_MOD = -.2
INV_MOD = .2
SKILL_SIGMA = .2

PEEK_ALARM_PENALTY = .2

# Map from alarm thresholds to corresponding observation skill
OBS_THRESHS = {
    0.: 0.,
    .5: .2,
    1: .4
}

RELAX_DEC = -.1

# Skills used for each action
ACTION_TO_SKILL = {

    'wait': 'stealth',  # Just a placeholderr

    'look_around': 'observation',
    'peek': 'observation',
    'investigate': 'observation',

    'hide': 'stealth',
    'take_out': 'hand_to_hand',
    'shoot': 'firearms',

    'bypass': 'acrobatics',
    'capture': 'stealth',
    # This is not used for the action itself. it is trumped by the objective's required skill. it is just used for alarm increase calculation

    'sneak': 'stealth',
    'charge': 'firearms',
    'exfiltrate': 'stealth'

}

ACTION_TO_COUNTER_SKILL = {
    'hide': 'observation',
    'take_out': 'hand_to_hand',
    'shoot': 'cover',
}