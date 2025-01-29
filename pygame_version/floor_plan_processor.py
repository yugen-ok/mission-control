import cv2
import numpy as np
import json
import os
import sys


class FloorPlanProcessor:
    def __init__(self, image_path, scale_meter_per_pixel):
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Could not find image file: {image_path}")

        self.image = cv2.imread(image_path)
        if self.image is None:
            raise ValueError(f"Failed to load image: {image_path}")

        self.gray = cv2.cvtColor(self.image, cv2.COLOR_BGR2GRAY)
        self.scale = scale_meter_per_pixel
        self.rooms = {}

        print(f"Loaded image shape: {self.image.shape}")

    def preprocess_image(self):
        print("Preprocessing image...")
        # Create a copy of the grayscale image
        processed = self.gray.copy()

        # Apply Gaussian blur to reduce noise
        processed = cv2.GaussianBlur(processed, (5, 5), 0)

        # Apply adaptive thresholding
        binary = cv2.adaptiveThreshold(
            processed,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV,
            11,
            2
        )

        # Remove noise
        kernel = np.ones((3, 3), np.uint8)
        binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
        binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)

        # Show intermediate results
        cv2.imshow('Processed Binary', binary)
        cv2.waitKey(1000)

        return binary

    def detect_rooms(self, binary):
        print("Detecting rooms...")
        # Find contours
        contours, hierarchy = cv2.findContours(
            binary,
            cv2.RETR_TREE,
            cv2.CHAIN_APPROX_SIMPLE
        )

        print(f"Found {len(contours)} initial contours")

        # Draw contours for debugging
        debug_image = self.image.copy()
        cv2.drawContours(debug_image, contours, -1, (0, 255, 0), 2)
        cv2.imshow('Detected Contours', debug_image)
        cv2.waitKey(1000)

        min_area = 1000  # Minimum area threshold
        max_area = self.image.shape[0] * self.image.shape[1] * 0.5  # Maximum area threshold

        for idx, contour in enumerate(contours):
            area = cv2.contourArea(contour)

            if area < min_area or area > max_area:
                continue

            x, y, w, h = cv2.boundingRect(contour)
            print(f"Processing room {idx}: Area = {area}, Dimensions = {w}x{h}")

            room_id = f"room_{idx}"
            self.rooms[room_id] = {
                "x": int(x),
                "y": int(y),
                "width": int(w),
                "height": int(h),
                "color": "#E8E8E8",
                "connections": [],
                "name": f"Room {idx}",
                "description": f"Automatically detected room {idx}",
                "area": float(area)
            }

    def detect_room_types(self):
        print("Detecting room types...")
        room_types = {
            "north_entry": {"name": "North Entry", "color": "#E8E8E8"},
            "new_east_addition": {"name": "New East Addition", "color": "#E0E0E0"},
            "lobby": {"name": "Lobby", "color": "#F5F5F5"},
            "committee_room": {"name": "Committee Room", "color": "#D3D3D3"},
            "gallery": {"name": "Gallery", "color": "#E8E8E8"},
            "senate_chamber": {"name": "Senate Chamber", "color": "#F0F0F0"},
            "antechamber": {"name": "Antechamber", "color": "#E0E0E0"},
            "foyer": {"name": "Foyer", "color": "#E8E8E8"},
            "south_entry": {"name": "South Entry", "color": "#E8E8E8"},
            "loading_dock": {"name": "Loading Dock", "color": "#D3D3D3"}
        }

        sorted_rooms = sorted(self.rooms.items(), key=lambda x: x[1]['area'], reverse=True)

        for (room_id, room), (type_name, type_info) in zip(sorted_rooms[:len(room_types)], room_types.items()):
            room.update({
                "name": type_info["name"],
                "color": type_info["color"],
                "type": type_name
            })

    def detect_connections(self):
        print("Detecting connections...")
        room_ids = list(self.rooms.keys())
        threshold = 50  # Adjacency threshold in pixels

        for i, room1_id in enumerate(room_ids):
            for room2_id in room_ids[i + 1:]:
                room1 = self.rooms[room1_id]
                room2 = self.rooms[room2_id]

                x1, y1 = room1["x"], room1["y"]
                w1, h1 = room1["width"], room1["height"]
                x2, y2 = room2["x"], room2["y"]
                w2, h2 = room2["width"], room2["height"]

                if (abs((x1 + w1) - x2) < threshold or abs(x1 - (x2 + w2)) < threshold) and \
                        (y1 < (y2 + h2) and (y1 + h1) > y2):
                    room1["connections"].append(room2_id)
                    room2["connections"].append(room1_id)
                elif (abs((y1 + h1) - y2) < threshold or abs(y1 - (y2 + h2)) < threshold) and \
                        (x1 < (x2 + w2) and (x1 + w1) > x2):
                    room1["connections"].append(room2_id)
                    room2["connections"].append(room1_id)

    def process(self):
        print("Starting image processing...")
        binary = self.preprocess_image()
        self.detect_rooms(binary)
        self.detect_room_types()
        self.detect_connections()
        return self.rooms

    def export_to_json(self, output_path):
        with open(output_path, 'w') as f:
            json.dump(self.rooms, f, indent=2)
        print(f"Exported results to {output_path}")


def main():
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        image_path = os.path.join(script_dir, 'floor_plans', '29-composite_floor_plan.jpg')

        print(f"Looking for image at: {image_path}")

        SCALE = 0.1
        processor = FloorPlanProcessor(image_path, SCALE)
        rooms = processor.process()

        output_path = os.path.join(script_dir, 'floorplan.json')
        processor.export_to_json(output_path)

        print(f"\nDetected {len(rooms)} rooms:")
        for room_id, room in rooms.items():
            print(f"{room['name']}: {room['width']}x{room['height']} pixels, Area: {room['area']:.0f} pixels²")

    except Exception as e:
        print(f"Error: {str(e)}")
        print(f"Python version: {sys.version}")
        print(f"OpenCV version: {cv2.__version__}")
    finally:
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()