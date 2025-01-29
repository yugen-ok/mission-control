import pygame
import json

from entities import *
from utils import *


def get_agent_colors(agent):
    is_hidden = agent.is_hidden
    if is_hidden:
        # A more subdued, grey-green color for hidden agents
        inner_color = (100, 128, 100)
        outline_color = (100, 128, 100)
    else:
        # Brighter green for visible agents
        inner_color = (0, 128, 0)
        outline_color = (0, 128, 0)
    return inner_color, outline_color


def get_hostile_colors(hostile):
    alarm_level = hostile.alarm_level
    if alarm_level > 1:
        # Orange gradient for hostiles shooting
        inner_color = (200, 128, 0)  # Orange
        outline_color = (255, 180, 100)  # Softer orange

    elif alarm_level == 1:
        # Distinct color for hostiles at exactly alarm level 1 (Yellow warning)
        inner_color = (255, 165, 0)  # Bright orange (Alert stage)
        outline_color = (255, 200, 100)  # Softer orange

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
            'agent': '#3B82F6',
            'health_good': '#22C55E',
            'health_mid': '#F59E0B',
            'health_low': '#EF4444'
        }

        # Load config
        with open(config_path, 'r') as f:
            self.config = json.load(f)

        # Window setup - increased dimensions
        self.WINDOW_WIDTH = 1600
        self.WINDOW_HEIGHT = 1000
        self.screen = pygame.display.set_mode((self.WINDOW_WIDTH, self.WINDOW_HEIGHT))
        pygame.display.set_caption("Building Map Game")

        # Panel dimensions - adjusted for larger window
        self.MAP_PANEL = pygame.Rect(20, 20, 750, 600)
        self.DETAILS_PANEL = pygame.Rect(790, 20, 450, 600)
        self.CHAT_PANEL = pygame.Rect(1260, 20, 320, 600)
        self.AGENTS_PANEL = pygame.Rect(20, 640, 1560, 340)

        # Fonts

        # Create base font
        # Create bold font by enabling bold flag
        base_font_bold = pygame.font.Font(None, 16)
        base_font_bold.set_bold(True)

        self.fonts = {
            'title': pygame.font.Font(None, 32),
            'subtitle': pygame.font.Font(None, 24),
            'body': pygame.font.Font(None, 18),
            'small': pygame.font.Font(None, 16),
            'small_bold': base_font_bold

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

        self.wrapped_input = ""
        self.input_cursor_pos = 0
        self.input_box_height = 60  # Increased height for multi-line input

    def format_number(self, value):
        """Format numbers without trailing zeros"""
        if value == 1:
            return "1"
        elif value == 0:
            return "0"
        else:
            # Convert to string and remove trailing zeros
            return f"{value:.1f}".rstrip('0').rstrip('.')

    def draw_agents(self):
        """Draw the agents panel with all agent cards"""
        self.draw_panel(self.AGENTS_PANEL, "Assets")

        # Panel layout configuration
        card_width = 400
        card_height = 205
        cards_per_row = 4
        x_padding = 20
        y_padding = 50

        # Colors for skills section
        SKILL_LABEL_COLOR = (135, 206, 250)  # Light blue
        SKILL_VALUE_COLOR = (255, 255, 255)  # White for bold values
        BOX_COLOR = self.hex_to_rgb(self.COLORS['border'])  # Border color for boxes

        def draw_field_box(surface, x, y, width, height):
            """Helper function to draw a field box"""
            pygame.draw.rect(surface, BOX_COLOR, (x, y, width, height), 1, border_radius=3)

        for i, agent in enumerate(self.gc.get_entities(Agent)):
            # Calculate card position
            row = i // cards_per_row
            col = i % cards_per_row
            x = self.AGENTS_PANEL.x + 10 + (card_width + x_padding) * col
            y = self.AGENTS_PANEL.y + y_padding + (card_height + 10) * row

            # Draw card background and border
            pygame.draw.rect(self.screen, self.hex_to_rgb(self.COLORS['panel_bg']), (x, y, card_width, card_height))
            pygame.draw.rect(self.screen, self.hex_to_rgb(self.COLORS['agent']), (x, y, card_width, card_height), 2)

            # Draw agent name
            name_surface = self.fonts['subtitle'].render(agent.name, True, self.hex_to_rgb(self.COLORS['text']))
            self.screen.blit(name_surface, (x + 15, y + 15))

            # Draw health section
            health_percent = agent.health / agent.max_health
            health_color = self.hex_to_rgb(self.COLORS['health_good'])
            if health_percent < 0.3:
                health_color = self.hex_to_rgb(self.COLORS['health_low'])
            elif health_percent < 0.7:
                health_color = self.hex_to_rgb(self.COLORS['health_mid'])

            # Health text and box
            health_y = y + 45
            health_box_width = 290
            health_box_height = 24
            draw_field_box(self.screen, x + 12, health_y, health_box_width, health_box_height)

            # Center the text inside the health box
            text_y = health_y + 2 + (health_box_height - self.fonts['small'].get_height()) // 2
            health_label = self.fonts['small'].render("Health: ", True, self.hex_to_rgb(self.COLORS['subtext']))
            health_value = self.fonts['small_bold'].render(f"{int(health_percent * 100)}%", True, health_color)
            self.screen.blit(health_label, (x + 16, text_y))
            self.screen.blit(health_value, (x + 16 + health_label.get_width(), text_y))

            # Health bar
            bar_width = 170
            bar_height = 6
            health_width = int(bar_width * health_percent)
            if health_width > 0:
                pygame.draw.rect(self.screen, health_color,
                                 (x + 110, health_y + (health_box_height // 2) - 3, health_width, bar_height))

            # Status and Location row
            status_y = y + 75
            status_box_width = 170
            status_box_height = 24
            draw_field_box(self.screen, x + 12, status_y, status_box_width, status_box_height)

            location_box_width = 190
            draw_field_box(self.screen, x + 192, status_y, location_box_width, status_box_height)

            # Center the text inside Status and Location boxes
            text_y = status_y + (status_box_height - self.fonts['small'].get_height()) // 2
            status_label = self.fonts['small'].render("Status: ", True, self.hex_to_rgb(self.COLORS['subtext']))
            status_value = self.fonts['small_bold'].render("Hidden" if agent.is_hidden else "Visible", True,
                                                           self.hex_to_rgb(self.COLORS['subtext']))
            self.screen.blit(status_label, (x + 16, text_y))
            self.screen.blit(status_value, (x + 16 + status_label.get_width(), text_y))

            location_label = self.fonts['small'].render("Location: ", True, self.hex_to_rgb(self.COLORS['subtext']))
            location_value = self.fonts['small_bold'].render(agent.area.name, True,
                                                             self.hex_to_rgb(self.COLORS['subtext']))
            self.screen.blit(location_label, (x + 196, text_y))
            self.screen.blit(location_value, (x + 196 + location_label.get_width(), text_y))

            # Skills title
            skills_title_y = y + 120  # Increased spacing (was 105)
            skills_title = self.fonts['body'].render("Skills", True, self.hex_to_rgb(self.COLORS['text']))
            self.screen.blit(skills_title, (x + 15, skills_title_y))

            def render_skill(skill_name, skill_value, pos_x, pos_y):
                """Draw skill name and value inside a field box with vertically centered text"""
                box_width = 170
                box_height = 24
                draw_field_box(self.screen, pos_x - 2, pos_y, box_width, box_height)

                # Center text within the skill box
                text_y = pos_y + (box_height - self.fonts['small'].get_height()) // 2
                label_surface = self.fonts['small'].render(f"{skill_name}: ", True, SKILL_LABEL_COLOR)
                self.screen.blit(label_surface, (pos_x + 2, text_y))

                value_surface = self.fonts['small_bold'].render(str(self.format_number(skill_value)), True,
                                                                SKILL_VALUE_COLOR)
                value_x = pos_x + 2 + label_surface.get_width()
                self.screen.blit(value_surface, (value_x, text_y))

            # Draw skills section
            skills_y = skills_title_y + 20
            col1_x = x + 15
            col2_x = x + 210

            # Draw left column skills
            render_skill("Stealth", agent.skills['stealth'], col1_x, skills_y)
            render_skill("Firearms", agent.skills['firearms'], col1_x, skills_y + 30)

            # Draw right column skills
            render_skill("Observation", agent.skills['observation'], col2_x, skills_y)
            render_skill("Hacking", agent.skills['hacking'], col2_x, skills_y + 30)

    def hex_to_rgb(self, hex_color: str) -> tuple[int, ...]:
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))

    def draw_panel(self, rect: pygame.Rect, title: str):
        pygame.draw.rect(self.screen, self.hex_to_rgb(self.COLORS['panel_bg']), rect)
        pygame.draw.rect(self.screen, self.hex_to_rgb(self.COLORS['border']), rect, 1)
        title_surface = self.fonts['title'].render(title, True, self.hex_to_rgb(self.COLORS['text']))
        self.screen.blit(title_surface, (rect.x + 10, rect.y + 10))


    def draw_connection(self, connection):
        area1 = connection.area1
        area2 = connection.area2
        conn_type = connection.conn_type


        x1 = self.MAP_PANEL.x + 20 + area1.x * self.scale_factor
        y1 = self.MAP_PANEL.y + 20 + area1.y * self.scale_factor
        x2 = self.MAP_PANEL.x + 20 + area2.x * self.scale_factor
        y2 = self.MAP_PANEL.y + 20 + area2.y * self.scale_factor
        w1 = area1.width * self.scale_factor
        h1 = area1.height * self.scale_factor
        w2 = area2.width * self.scale_factor
        h2 = area2.height * self.scale_factor

        if conn_type == 'open':
            color = '#E8E8E8'
        elif conn_type == 'door':
            color = '#000000'
        elif conn_type == 'window':
            color = '#4169E1'
        else:
            color = '#E8E8E8'
        # Check for vertical alignment (shared vertical wall)
        if (abs(x1 + w1 - x2) < 1 or abs(x2 + w2 - x1) < 1):
            # Find overlapping y-range
            top = max(y1, y2)
            bottom = min(y1 + h1, y2 + h2)
            if bottom > top:  # If there is overlap
                center_y = top + (bottom - top) / 2
                if x1 < x2:  # area1 is to the left of area2
                    pygame.draw.rect(self.screen, color,
                                     (x2 - 2, center_y - 5, 4, 10))
                else:  # area1 is to the right of area2
                    pygame.draw.rect(self.screen, color,
                                     (x1 - 2, center_y - 5, 4, 10))

        # Check for horizontal alignment (shared horizontal wall)
        elif (abs(y1 + h1 - y2) < 1 or abs(y2 + h2 - y1) < 1):
            # Find overlapping x-range
            left = max(x1, x2)
            right = min(x1 + w1, x2 + w2)
            if right > left:  # If there is overlap
                center_x = left + (right - left) / 2
                if y1 < y2:  # area1 is above area2
                    pygame.draw.rect(self.screen, color,
                                     (center_x - 5, y2 - 2, 10, 4))
                else:  # area1 is below area2
                    pygame.draw.rect(self.screen, color,
                                     (center_x - 5, y1 - 2, 10, 4))

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

                    random.setstate(
                        previous_state)  # Reset the random state to its previous state to avoid conflicts with other agents' positions'

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

                    random.setstate(
                        previous_state)  # Reset the random state to its previous state to avoid conflicts with other agents' positions'

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

                    random.setstate(
                        previous_state)  # Reset the random state to its previous state to avoid conflicts with other agents' positions'

                    inner_color, outline_color = get_objective_colors(objective)

                    # Draw the objective
                    pygame.draw.circle(self.screen, outline_color, (blue_dot_x, blue_dot_y),
                                       7)  # outline (outer circle)
                    pygame.draw.circle(self.screen, inner_color,
                                       (blue_dot_x, blue_dot_y), 5)  # Inner circle

        for area in self.gc.get_entities(Area):
            for connection in area.connections:
                self.draw_connection(connection)

    def wrap_input_text(self, text, font, max_width):
        """Wrap input text and handle cursor position"""
        words = text.split(' ')
        lines = []
        current_line = ""

        for word in words:
            test_line = current_line + (" " if current_line else "") + word
            if font.size(test_line)[0] <= max_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                    current_line = word
                else:
                    # If a single word is too long, force-break it
                    lines.append(word)
                    current_line = ""

        if current_line:
            lines.append(current_line)

        return '\n'.join(lines)

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
                objectives_in_area = [objective for objective in self.gc.get_entities(Objective) if
                                      objective.area == area]

                # Display agents
                if agents_in_area:
                    agent_surface = self.fonts['body'].render("Agents:", True, self.hex_to_rgb(self.COLORS['subtext']))
                    self.screen.blit(agent_surface, (self.DETAILS_PANEL.x + 10, self.DETAILS_PANEL.y + y_offset))

                if agents_in_area:
                    for agent in agents_in_area:
                        y_offset += 20
                        agent_name_surface = self.fonts['small'].render(f"• {agent.name}", True,
                                                                        self.hex_to_rgb(self.COLORS['text']))
                        self.screen.blit(agent_name_surface,
                                         (self.DETAILS_PANEL.x + 20, self.DETAILS_PANEL.y + y_offset))

                if hostiles_in_area and (agents_in_area or any([hostile.is_peeked for hostile in hostiles_in_area])):
                    y_offset += 20
                    # Display hostiles
                    hostile_surface = self.fonts['body'].render("Hostiles:", True,
                                                                self.hex_to_rgb(self.COLORS['subtext']))
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
                    hostile_surface = self.fonts['body'].render("Objectives:", True,
                                                                self.hex_to_rgb(self.COLORS['subtext']))
                    self.screen.blit(hostile_surface, (self.DETAILS_PANEL.x + 10, self.DETAILS_PANEL.y + y_offset))

                for objective in objectives_in_area:
                    y_offset += 20
                    objective_name_surface = self.fonts['small'].render(f"• {objective.name}", True,
                                                                        self.hex_to_rgb(self.COLORS['text']))
                    self.screen.blit(objective_name_surface,
                                     (self.DETAILS_PANEL.x + 20, self.DETAILS_PANEL.y + y_offset))

    def draw_chat(self):
        self.draw_panel(self.CHAT_PANEL, "Mission Log")
        y_offset = 60
        max_message_width = self.CHAT_PANEL.width - 20

        # Calculate the height needed for the input box
        input_box = pygame.Rect(
            self.CHAT_PANEL.x + 10,
            self.CHAT_PANEL.bottom - self.input_box_height,
            self.CHAT_PANEL.width - 20,
            self.input_box_height
        )

        # Adjust message display area to account for larger input box
        messages_area_height = self.CHAT_PANEL.height - 70 - self.input_box_height

        # Display messages with improved wrapping
        visible_messages = []
        current_height = 0

        for message in reversed(self.chat_messages):
            wrapped_lines = self.wrap_text(message, self.fonts['small'], max_message_width)
            message_height = len(wrapped_lines) * self.fonts['small'].get_linesize()

            if current_height + message_height > messages_area_height:
                break

            visible_messages.insert(0, (wrapped_lines, message_height))
            current_height += message_height

        # Render visible messages
        current_y = y_offset
        for wrapped_lines, _ in visible_messages:
            for line in wrapped_lines:
                msg_surface = self.fonts['small'].render(line, True, self.hex_to_rgb(self.COLORS['text']))
                self.screen.blit(msg_surface, (self.CHAT_PANEL.x + 10, self.CHAT_PANEL.y + current_y))
                current_y += self.fonts['small'].get_linesize()

        # Draw input box with wrapped text
        pygame.draw.rect(self.screen, self.hex_to_rgb(self.COLORS['panel_bg']), input_box)
        pygame.draw.rect(self.screen, self.hex_to_rgb(self.COLORS['border']), input_box, 1)

        # Update wrapped input text
        wrapped_input = self.wrap_input_text(self.chat_input, self.fonts['small'], max_message_width)

        # Render wrapped input text
        input_y = input_box.y + 5
        for line in wrapped_input.split('\n'):
            input_surface = self.fonts['small'].render(line, True, self.hex_to_rgb(self.COLORS['text']))
            self.screen.blit(input_surface, (input_box.x + 5, input_y))
            input_y += self.fonts['small'].get_linesize()

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
