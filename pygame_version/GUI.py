import pygame
import json

from entities import *
from utils import *


def get_agent_colors(agent):
    is_hidden = agent.is_hidden
    if is_hidden:
        # A more subdued, grey-green color for hidden agents
        inner_color = (50, 80, 50)
        outline_color = (80, 120, 80)
    else:
        # Brighter green for visible agents
        inner_color = (0, 128, 0)
        outline_color = (0, 200, 0)
    return inner_color, outline_color


def get_hostile_colors(hostile):
    alarm_level = hostile.alarm_level
    if alarm_level > 1:
        # Orange gradient for hostiles shooting
        inner_color = (200, 128, 0)  # Orange
        outline_color = (255, 180, 100)  # Softer orange

    elif alarm_level > 0.5:
        # Brighter red for suspicious hostiles
        inner_color = (255, 0, 0)  # Bright red
        outline_color = (255, 100, 100)  # Lighter red
    else:
        # Normal red for idle hostiles
        inner_color = (160, 0, 0)
        outline_color = (200, 0, 0)
    return inner_color, outline_color


def get_objective_colors(objective):
    is_captured = objective.is_captured
    if is_captured:
        # A more subdued, grey-green color for hidden agents
        inner_color = (50, 50, 150)
        outline_color = (0, 0, 100)
    else:
        # Brighter green for visible agents
        inner_color = (0, 0, 255)
        outline_color = (0, 0, 100)
    return inner_color, outline_color


import time


class GUI:
    def __init__(self, config_path: str, gc: GameController):
        pygame.init()

        self.gc = gc  # Game controller instance

        # Colors
        self.COLORS = {
            'background': '#1A1A1A',
            'panel_bg': '#2A2A2A',
            'text': '#FFFFFF',
            'subtext': '#AAAAAA',
            'highlight': '#3B82F6',
            'border': '#404040',
            'agent': '#3B82F6'
        }

        # Load config
        with open(config_path, 'r') as f:
            self.config = json.load(f)

        # Window setup
        self.WINDOW_WIDTH = 1350
        self.WINDOW_HEIGHT = 800
        self.screen = pygame.display.set_mode((self.WINDOW_WIDTH, self.WINDOW_HEIGHT))
        pygame.display.set_caption("Building Map Game")

        # Panel dimensions
        self.MAP_PANEL = pygame.Rect(20, 20, 600, 500)
        self.DETAILS_PANEL = pygame.Rect(640, 20, 360, 500)
        self.CHAT_PANEL = pygame.Rect(1020, 20, 300, 500)
        self.AGENTS_PANEL = pygame.Rect(20, 540, 1300, 240)

        # Fonts
        self.fonts = {
            'title': pygame.font.Font(None, 32),
            'subtitle': pygame.font.Font(None, 24),
            'body': pygame.font.Font(None, 18),
            'small': pygame.font.Font(None, 16)
        }

        # Parse areas and calculate scaling
        self.scale_factor = min(
            (self.MAP_PANEL.width - 40) / self.config['mapWidth'],
            (self.MAP_PANEL.height - 40) / self.config['mapHeight']
        )

        # Selected area for details panel
        self.selected_area = None

        # Chat messages and input
        self.chat_messages = []
        self.chat_input = ""

    def hex_to_rgb(self, hex_color: str) -> tuple[int, ...]:
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))

    def draw_panel(self, rect: pygame.Rect, title: str):
        pygame.draw.rect(self.screen, self.hex_to_rgb(self.COLORS['panel_bg']), rect)
        pygame.draw.rect(self.screen, self.hex_to_rgb(self.COLORS['border']), rect, 1)
        title_surface = self.fonts['title'].render(title, True, self.hex_to_rgb(self.COLORS['text']))
        self.screen.blit(title_surface, (rect.x + 10, rect.y + 10))

    def draw_connection_hollow(self, area1: Area, area2: Area):
        x1 = self.MAP_PANEL.x + 20 + area1.x * self.scale_factor
        y1 = self.MAP_PANEL.y + 20 + area1.y * self.scale_factor
        x2 = self.MAP_PANEL.x + 20 + area2.x * self.scale_factor
        y2 = self.MAP_PANEL.y + 20 + area2.y * self.scale_factor
        w1 = area1.width * self.scale_factor
        h1 = area1.height * self.scale_factor
        w2 = area2.width * self.scale_factor
        h2 = area2.height * self.scale_factor

        if abs(x1 - x2) < 1:  # Vertical connection
            center_x = x1 + w1 / 2
            if y1 < y2:
                pygame.draw.rect(self.screen, self.hex_to_rgb(self.COLORS['panel_bg']),
                                 (center_x - 5, y1 + h1 - 2, 10, 4))
            else:
                pygame.draw.rect(self.screen, self.hex_to_rgb(self.COLORS['panel_bg']),
                                 (center_x - 5, y2 + h2 - 2, 10, 4))
        elif abs(y1 - y2) < 1:  # Horizontal connection
            center_y = y1 + h1 / 2
            if x1 < x2:
                pygame.draw.rect(self.screen, self.hex_to_rgb(self.COLORS['panel_bg']),
                                 (x1 + w1 - 2, center_y - 5, 4, 10))
            else:
                pygame.draw.rect(self.screen, self.hex_to_rgb(self.COLORS['panel_bg']),
                                 (x2 + w2 - 2, center_y - 5, 4, 10))

    def draw_map(self):

        self.draw_panel(self.MAP_PANEL, "Building Map")

        # Dictionary to store each agent's position within their current area
        agent_positions = {}

        for area in self.gc.get_entities(Area):
            x = self.MAP_PANEL.x + 20 + area.x * self.scale_factor
            y = self.MAP_PANEL.y + 20 + area.y * self.scale_factor
            width = area.width * self.scale_factor
            height = area.height * self.scale_factor

            # Draw the area rectangle
            pygame.draw.rect(self.screen, self.hex_to_rgb(area.color),
                             (x, y, width, height))
            pygame.draw.rect(self.screen, self.hex_to_rgb(self.COLORS['border']),
                             (x, y, width, height), 1)

            # Draw area name inside a text box
            margin = 4  # Margin inside the area for the text box
            text_box_width = width - 2 * margin
            text_box_height = height - 2 * margin

            # Wrap and render text
            font = self.fonts['small']
            text_lines = self.wrap_text(area.name, font, text_box_width)
            line_height = font.get_linesize()

            # Adjust for vertical centering
            total_text_height = len(text_lines) * line_height
            y_offset = y + margin + (text_box_height - total_text_height) / 2

            for line in text_lines:
                text_surface = font.render(line, True, (0, 0, 0))  # Black color
                text_rect = text_surface.get_rect(center=(x + width / 2, y_offset + line_height / 2))
                self.screen.blit(text_surface, text_rect)
                y_offset += line_height

                # Check if the area contains any agents
            agents_in_area = [agent for agent in self.gc.get_entities(Agent) if agent.area == area]
            for agent in agents_in_area:
                if agent.name not in agent_positions:
                    # Generate a random position within the area for the agent

                    previous_state = random.getstate()
                    unique_seed = encode_uuids_to_integer(agent.id, area.id)
                    random.seed(unique_seed)

                    dot_x = random.randint(int(x + margin), int(x + width - margin))
                    dot_y = random.randint(int(y + margin), int(y + height - margin))

                    random.setstate(previous_state)  # Reset the random state to its previous state to avoid conflicts with other agents' positions'

                    agent_positions[agent.name] = (dot_x, dot_y)


                else:
                    # Use the previously stored position
                    dot_x, dot_y = agent_positions[agent.name]

                # Get colors based on agent's hidden status
                inner_color, outline_color = get_agent_colors(agent)

                # Draw the agent
                pygame.draw.circle(self.screen, outline_color, (dot_x, dot_y), 7)  # outline (outer circle)
                pygame.draw.circle(self.screen, inner_color, (dot_x, dot_y), 5)  # Inner circle

            # Check if the area contains any hostiles
            hostiles_in_area = [hostile for hostile in self.gc.get_entities(Hostile) if hostile.area == area]
            for hostile in hostiles_in_area:
                if agents_in_area or hostile.is_peeked or self.gc.hostiles_visible:

                    previous_state = random.getstate()
                    unique_seed = encode_uuids_to_integer(area.id, hostile.id)
                    random.seed(unique_seed)

                    red_dot_x = random.randint(int(x + margin), int(x + width - margin))
                    red_dot_y = random.randint(int(y + margin), int(y + height - margin))

                    random.setstate(previous_state)  # Reset the random state to its previous state to avoid conflicts with other agents' positions'

                    # Get colors based on hostile's alarm level
                    inner_color, outline_color = get_hostile_colors(hostile)

                    # Draw the hostile
                    pygame.draw.circle(self.screen, outline_color, (red_dot_x, red_dot_y),
                                       7)  # outline (outer circle)
                    pygame.draw.circle(self.screen, inner_color, (red_dot_x, red_dot_y), 5)  # Inner circle

            objectives_in_area = [objective for objective in self.gc.get_entities(Objective) if
                                  objective.area == area]

            for objective in objectives_in_area:
                if objective.get_explored() > 1:

                    previous_state = random.getstate()

                    unique_seed = encode_uuids_to_integer(area.id, objective.id)
                    random.seed(unique_seed)

                    blue_dot_x = random.randint(int(x + margin), int(x + width - margin))
                    blue_dot_y = random.randint(int(y + margin), int(y + height - margin))

                    random.setstate(previous_state)  # Reset the random state to its previous state to avoid conflicts with other agents' positions'

                    inner_color, outline_color = get_objective_colors(objective)

                    # Draw the objective
                    pygame.draw.circle(self.screen, outline_color, (blue_dot_x, blue_dot_y),
                                       7)  # outline (outer circle)
                    pygame.draw.circle(self.screen, inner_color,
                                       (blue_dot_x, blue_dot_y), 5)  # Inner circle

        for area in self.gc.get_entities(Area):
            for connection in area.connections:
                self.draw_connection_hollow(area, connection.get_other_area(area))

    def wrap_text(self, text, font, max_width):
        words = text.split(' ')
        lines = []
        current_line = ""

        for word in words:
            test_line = current_line + (" " if current_line else "") + word
            if font.size(test_line)[0] <= max_width:
                current_line = test_line
            else:
                lines.append(current_line)
                current_line = word

        if current_line:
            lines.append(current_line)

        return lines

    def draw_area_details(self):
        self.draw_panel(self.DETAILS_PANEL, "Details")
        if self.selected_area:
            area = next((a for a in self.gc.get_entities(Area) if a.name == self.selected_area), None)
            if area:
                y_offset = 60

                name_surface = self.fonts['subtitle'].render(area.name, True, self.hex_to_rgb(self.COLORS['text']))
                self.screen.blit(name_surface, (self.DETAILS_PANEL.x + 10, self.DETAILS_PANEL.y + y_offset))

                y_offset += 30

                # Wrap and render area description
                description_lines = self.wrap_text(area.description, self.fonts['body'], self.DETAILS_PANEL.width - 20)
                for line in description_lines:
                    desc_surface = self.fonts['body'].render(line, True, self.hex_to_rgb(self.COLORS['subtext']))
                    self.screen.blit(desc_surface, (self.DETAILS_PANEL.x + 10, self.DETAILS_PANEL.y + y_offset))
                    y_offset += self.fonts['body'].get_linesize()

                y_offset += 40
                agents_in_area = [agent for agent in self.gc.get_entities(Agent) if agent.area == area]
                hostiles_in_area = [hostile for hostile in self.gc.get_entities(Hostile) if
                                    hostile.area == area]
                objectives_in_area = [objective for objective in self.gc.get_entities(Objective) if objective.area == area]

                # Display agents
                if agents_in_area:
                    agent_surface = self.fonts['body'].render("Agents:", True, self.hex_to_rgb(self.COLORS['subtext']))
                    self.screen.blit(agent_surface, (self.DETAILS_PANEL.x + 10, self.DETAILS_PANEL.y + y_offset))

                if agents_in_area:
                    for agent in agents_in_area:
                        y_offset += 20
                        agent_name_surface = self.fonts['small'].render(f"• {agent.name}", True,
                                                                        self.hex_to_rgb(self.COLORS['text']))
                        self.screen.blit(agent_name_surface, (self.DETAILS_PANEL.x + 20, self.DETAILS_PANEL.y + y_offset))

                if hostiles_in_area and (agents_in_area or any([hostile.is_peeked for hostile in hostiles_in_area])):
                    y_offset += 20
                    # Display hostiles
                    hostile_surface = self.fonts['body'].render("Hostiles:", True, self.hex_to_rgb(self.COLORS['subtext']))
                    self.screen.blit(hostile_surface, (self.DETAILS_PANEL.x + 10, self.DETAILS_PANEL.y + y_offset))

                for hostile in hostiles_in_area:
                    if agents_in_area or hostile.is_peeked:
                        y_offset += 20
                        hostile_name_surface = self.fonts['small'].render(f"• {hostile.name}", True,
                                                                          self.hex_to_rgb(self.COLORS['text']))
                        self.screen.blit(hostile_name_surface,
                                         (self.DETAILS_PANEL.x + 20, self.DETAILS_PANEL.y + y_offset))

                if objectives_in_area:
                    y_offset += 20
                    # Display hostiles
                    hostile_surface = self.fonts['body'].render("Objectives:", True, self.hex_to_rgb(self.COLORS['subtext']))
                    self.screen.blit(hostile_surface, (self.DETAILS_PANEL.x + 10, self.DETAILS_PANEL.y + y_offset))


                for objective in objectives_in_area:
                    y_offset += 20
                    objective_name_surface = self.fonts['small'].render(f"• {objective.name}", True,
                                                                          self.hex_to_rgb(self.COLORS['text']))
                    self.screen.blit(objective_name_surface,
                                     (self.DETAILS_PANEL.x + 20, self.DETAILS_PANEL.y + y_offset))

    def draw_chat(self):
        self.draw_panel(self.CHAT_PANEL, "Mission Log")
        y_offset = 60  # Start rendering messages below the title

        # Maximum width for wrapping messages inside the chat panel
        max_message_width = self.CHAT_PANEL.width - 20  # Subtracting padding for the text

        # Loop through the last 15 chat messages and wrap each one
        for message in self.chat_messages[-15:]:  # Show last 15 messages
            wrapped_lines = self.wrap_text(message, self.fonts['small'], max_message_width)
            for line in wrapped_lines:
                msg_surface = self.fonts['small'].render(line, True, self.hex_to_rgb(self.COLORS['text']))
                self.screen.blit(msg_surface, (self.CHAT_PANEL.x + 10, self.CHAT_PANEL.y + y_offset))
                y_offset += self.fonts['small'].get_linesize()

        # Draw the input box at the bottom of the chat panel
        input_box = pygame.Rect(self.CHAT_PANEL.x + 10, self.CHAT_PANEL.bottom - 30, self.CHAT_PANEL.width - 20, 20)
        pygame.draw.rect(self.screen, self.hex_to_rgb(self.COLORS['panel_bg']), input_box)
        pygame.draw.rect(self.screen, self.hex_to_rgb(self.COLORS['border']), input_box, 1)

        # Render the current chat input
        input_surface = self.fonts['small'].render(self.chat_input, True, self.hex_to_rgb(self.COLORS['text']))
        self.screen.blit(input_surface, (input_box.x + 5, input_box.y + 2))

    def draw_agents(self):
        self.draw_panel(self.AGENTS_PANEL, "Assets")

        card_width = 270
        card_height = 90
        cards_per_row = 4
        x_padding = 20
        y_padding = 50

        for i, agent in enumerate(self.gc.get_entities(Agent)):
            row = i // cards_per_row
            col = i % cards_per_row

            x = self.AGENTS_PANEL.x + 10 + (card_width + x_padding) * col
            y = self.AGENTS_PANEL.y + y_padding + (card_height + 10) * row

            pygame.draw.rect(self.screen, self.hex_to_rgb(self.COLORS['panel_bg']),
                             (x, y, card_width, card_height))
            pygame.draw.rect(self.screen, self.hex_to_rgb(self.COLORS['agent']),
                             (x, y, card_width, card_height), 2)

            name_surface = self.fonts['subtitle'].render(agent.name, True, self.hex_to_rgb(self.COLORS['text']))
            self.screen.blit(name_surface, (x + 10, y + 10))

            status_surface = self.fonts['small'].render(f"Hidden: {agent.is_hidden}", True,
                                                        self.hex_to_rgb(self.COLORS['subtext']))
            self.screen.blit(status_surface, (x + 10, y + 40))

            location_surface = self.fonts['small'].render(f"Location: {agent.area.name}", True,
                                                          self.hex_to_rgb(self.COLORS['subtext']))
            self.screen.blit(location_surface, (x + 10, y + 60))

    def handle_click(self, pos):
        if self.MAP_PANEL.collidepoint(pos):
            relative_x = pos[0] - (self.MAP_PANEL.x + 20)
            relative_y = pos[1] - (self.MAP_PANEL.y + 20)

            for area in self.gc.get_entities(Area):
                scaled_x = area.x * self.scale_factor
                scaled_y = area.y * self.scale_factor
                scaled_width = area.width * self.scale_factor
                scaled_height = area.height * self.scale_factor

                if (scaled_x <= relative_x <= scaled_x + scaled_width and
                        scaled_y <= relative_y <= scaled_y + scaled_height):
                    self.selected_area = area.name
                    break

    def handle_input(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_RETURN:  # Submit message
                control_message = 'Control: ' + self.chat_input.strip()
                self.chat_messages.append(control_message)
                self.chat_input = ""
                self.gc.mission_log.append(control_message, push_to_queue=False)
                self.gc.process_turn()

                while len(self.gc.mission_log.print_queue) > 0:
                    self.chat_messages.append(self.gc.mission_log.print_queue.popleft())

            elif event.key == pygame.K_BACKSPACE:  # Delete character
                self.chat_input = self.chat_input[:-1]
            else:
                self.chat_input += event.unicode

    def run(self):
        running = True
        clock = pygame.time.Clock()

        while running:

            for event in pygame.event.get():

                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:
                        self.handle_click(event.pos)
                elif event.type in [pygame.KEYDOWN, pygame.KEYUP]:
                    self.handle_input(event)

            self.screen.fill(self.hex_to_rgb(self.COLORS['background']))
            self.draw_map()
            self.draw_area_details()
            self.draw_chat()
            self.draw_agents()

            pygame.display.flip()
            clock.tick(60)

        pygame.quit()
