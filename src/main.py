## 2025, UNL Aerospace Club
## Licensed under the GNU General Public License version 3
#
# Program to calculate angles for a dish given two GPS coordinates
#
# Lots of useful formulas for things used here:
# https://www.movable-type.co.uk/scripts/latlong.html

from typing import Any, Optional
import customtkinter
from tkintermapview import TkinterMapView
import serial
from threading import Thread
import json
import signal
from tkinter import ttk
import tkinter as tk


## LOCAL IMPORTS ##
from rotator import Rotator
from utils import GPSPoint, crc32

# Spaceport:    32.940058,  -106.921903
# Texas Place:  31.046083,  -103.543556
# Lincoln:      40.82320,    -96.69693
DEFAULT_LAT = 40.82320
DEFAULT_LON = -96.69693

# Global variable storing rocket packet data
ROCKET_PACKET_CONT = None

class App(customtkinter.CTk):

    APP_NAME = "ARCHER/AROWSS - UNL Aerospace"
    WIDTH = 1024
    HEIGHT = 768

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.title(App.APP_NAME)
        self.geometry(str(self.WIDTH) + "x" + str(self.HEIGHT))
        self.minsize(App.WIDTH, App.HEIGHT)

        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        # ============ create two CTkFrames ============

        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.frame_left = customtkinter.CTkFrame(master=self, width=400, corner_radius=0, fg_color=None)
        self.frame_left.grid(row=0, column=0, padx=0, pady=0, sticky="nsew")
        self.frame_left.grid_propagate(False)

        self.frame_right = customtkinter.CTkFrame(master=self, corner_radius=0)
        self.frame_right.grid(row=0, column=1, rowspan=1, pady=0, padx=0, sticky="nsew")

        # ============ frame_left ============

        self.frame_left.grid_columnconfigure(0, weight=1)

        # Telemetry display
        self.telemetry = Telemetry(master=self.frame_left, command=self.set_ground_parameters)
        self.telemetry.grid(pady=20)

        # Ground position settings
        self.ground_settings = GroundSettings(master=self.frame_left, command=self.set_ground_parameters)
        self.ground_settings.grid()

        # Map style settings
        self.map_label = customtkinter.CTkLabel(self.frame_left, text="Map Style:", anchor="w")
        self.map_label.grid(padx=(20, 20), pady=(20, 0))
        self.map_option_menu = customtkinter.CTkOptionMenu(self.frame_left, values=["Google hybrid", "Google normal", "Google satellite", "OpenStreetMap"], command=self.change_map)
        self.map_option_menu.grid(padx=(20, 20), pady=(0, 20))

        # ============ frame_right ============

        self.frame_right.grid_rowconfigure(1, weight=1)
        self.frame_right.grid_rowconfigure(0, weight=0)
        self.frame_right.grid_columnconfigure(0, weight=1)
        self.frame_right.grid_columnconfigure(1, weight=0)
        self.frame_right.grid_columnconfigure(2, weight=1)

        self.map_widget = TkinterMapView(self.frame_right, corner_radius=0)
        self.map_widget.grid(row=1, rowspan=1, column=0, columnspan=3, sticky="nswe", padx=(0, 0), pady=(0, 0))

        # Right click event handling
        self.map_widget.add_right_click_menu_command(
            label="Set Ground Position",
            command=self.right_click_ground_position,
            pass_coords=True
        )

        # Set default value
        self.map_widget.set_position(DEFAULT_LAT, DEFAULT_LON)
        self.map_widget.set_zoom(16)
        self.map_option_menu.set("Google hybrid")
        self.map_widget.set_tile_server("https://mt0.google.com/vt/lyrs=y&hl=en&x={x}&y={y}&z={z}&s=Ga", max_zoom=22)

    def set_ground_parameters(self):
        try:
            lat_str = self.ground_settings.latitude.get()
            if lat_str is not None and lat_str != '':
                self.ground_position.lat = float(lat_str)

            lon_str = self.ground_settings.longitude.get()
            if lon_str is not None and lon_str != '':
                self.ground_position.lon = float(lon_str)

            alt_str = self.ground_settings.altitude.get()
            if alt_str is not None and alt_str != '':
                self.ground_position.alt = float(alt_str)
        except ValueError as e:
            print(f"Invalid value! {e}")


        if self.ground_marker is not None:
            self.ground_marker.set_position(
                self.ground_position.lat,
                self.ground_position.lon
            )
        else:
            self.ground_marker = self.map_widget.set_marker(
                self.ground_position.lat,
                self.ground_position.lon
            )

    def right_click_ground_position(self, coords):
        if self.ground_marker is not None:
            self.ground_marker.set_position(coords[0], coords[1])
        else:
            self.ground_marker = self.map_widget.set_marker(coords[0], coords[1])

        self.ground_position = GPSPoint(coords[0], coords[1], self.ground_position.alt)

        self.ground_settings.latitude.set(coords[0])
        self.ground_settings.longitude.set(coords[1])
        self.ground_settings.altitude.set(str(self.ground_position.alt))

    def set_air_position(self):

        #print("function ran yay")
        if ROCKET_PACKET_CONT is None or "gps" not in ROCKET_PACKET_CONT:
            self.after(500, self.set_air_position)
            return

        gps_lat = ROCKET_PACKET_CONT["gps"]["latitude"]
        gps_lon = ROCKET_PACKET_CONT["gps"]["longitude"]
        gps_alt = ROCKET_PACKET_CONT["gps"]["altitude"]

        self.telemetry.lat.configure(text=f"{gps_lat:.8f}")
        self.telemetry.lon.configure(text=f"{gps_lon:.8f}")
        self.telemetry.alt.configure(text=f"{gps_alt:.2f}m")

        self.air_position = GPSPoint(gps_lat, gps_lon, gps_alt)

        # Update the marker for the air side
        if self.air_marker is not None:
            self.air_marker.set_position(gps_lat, gps_lon)
        else:
            self.air_marker = self.map_widget.set_marker(gps_lat, gps_lon)

        if self.ground_position is None:
            self.after(500, self.set_air_position)
            return

        # Straight line distance between the ground positions
        # distance = self.ground_position.distance_to(self.air_position)

        # Altitude above ground station position
        # altitude = self.ground_position.altitude_to(self.air_position)
        # if altitude is None:
        #    altitude = 0.0

        horiz = self.ground_position.bearing_mag_corrected_to(self.air_position)
        vert = self.ground_position.elevation_to(self.air_position)

        if self.rotator is not None:
            self.rotator.set_position_vertical(vert)
            self.rotator.set_position_horizontal(horiz)

        self.telemetry.rot_az.configure(text=f"{horiz:.1f}°")
        self.telemetry.rot_alt.configure(text=f"{vert:.1f}°")

        self.after(500, self.set_air_position)

    def change_map(self, new_map: str):
        match new_map:
            case "Google hybrid":
                self.map_widget.set_tile_server(
                    "https://mt0.google.com/vt/lyrs=y&hl=en&x={x}&y={y}&z={z}&s=Ga",
                    max_zoom=22
                )
            case "Google normal":
                self.map_widget.set_tile_server(
                    "https://mt0.google.com/vt/lyrs=m&hl=en&x={x}&y={y}&z={z}&s=Ga",
                    max_zoom=22
                )
            case "Google satellite":
                self.map_widget.set_tile_server(
                    "https://mt0.google.com/vt/lyrs=s&hl=en&x={x}&y={y}&z={z}&s=Ga",
                    max_zoom=22
                )
            case "OpenStreetMap":
                self.map_widget.set_tile_server(
                    "https://a.tile.openstreetmap.org/{z}/{x}/{y}.png",
                    max_zoom=22
                )

    def on_closing(self, signal=0, frame=None):
        print("Exiting!")
        self.destroy()

    def start(self):
        try:
            self.rotator = Rotator("/dev/ttyUSB1")
        except IOError:
            self.rotator = None

        # The ground station position
        self.ground_marker: Optional[Any] = None
        self.ground_position = GPSPoint(0, 0, 0)

        # Rocket position
        self.air_marker: Optional[Any] = None
        self.air_position = GPSPoint(0, 0, 0)

        self.after(500, self.set_air_position)

        self.mainloop()


class Telemetry(customtkinter.CTkFrame):
    def __init__(self, master, command, **kwargs):
        super().__init__(master, fg_color="transparent", border_width=0, **kwargs)

        customtkinter.CTkLabel(
            self,
            text="Telemetry:",
            anchor="w",
            font=("Noto Sans", 18)
        ).grid(columnspan=4, pady=(0, 5))

        sep = tk.Frame(self, bg="#474747", height=1, bd=0)
        sep.grid(row=1, columnspan=4, sticky="ew")

        customtkinter.CTkLabel(self, text="Latitude:").grid(row=2, column=0, padx=10)
        self.lat = customtkinter.CTkLabel(self, width=200, text="...", anchor="w")
        self.lat.grid(row=2, column=1, columnspan=4)

        customtkinter.CTkLabel(self, text="Longitude:").grid(row=3, column=0, padx=10)
        self.lon = customtkinter.CTkLabel(self, width=200, text="...", anchor="w")
        self.lon.grid(row=3, column=1, columnspan=4)

        customtkinter.CTkLabel(self, text="Altitude:").grid(row=4, column=0, padx=10)
        self.alt = customtkinter.CTkLabel(self, width=200, text="...", anchor="w")
        self.alt.grid(row=4, column=1, columnspan=4)

        sep = tk.Frame(self, bg="#474747", height=1, bd=0)
        sep.grid(row=5, columnspan=4, sticky="ew")

        customtkinter.CTkLabel(self, text="Elevation:").grid(row=6, column=0, padx=10)
        self.rot_alt = customtkinter.CTkLabel(self, width=50, text="...", anchor="w")
        self.rot_alt.grid(row=6, column=1)

        customtkinter.CTkLabel(self, text="Bearing:").grid(row=6, column=2, padx=10)
        self.rot_az = customtkinter.CTkLabel(self, width=50, text="...", anchor="w")
        self.rot_az.grid(row=6, column=3)

        sep = tk.Frame(self, bg="#474747", height=1, bd=0)
        sep.grid(row=7, columnspan=4, sticky="ew")


class GroundSettings(customtkinter.CTkFrame):
    def __init__(self, master, command, **kwargs):
        super().__init__(master, fg_color="transparent", border_width=0, **kwargs)

        customtkinter.CTkLabel(
            self,
            text="Ground Settings:",
            anchor="w",
            font=("Noto Sans", 18)
        ).grid(pady=(0, 5))

        self.latitude = LabeledTextEntry(self, label_text="Latitude")
        self.latitude.grid(pady=2.5, padx=5, sticky="w")

        self.longitude = LabeledTextEntry(self, label_text="Longitude")
        self.longitude.grid(pady=2.5, padx=5, sticky="w")

        self.altitude = LabeledTextEntry(self, label_text="Altitude")
        self.altitude.grid(pady=2.5, padx=5, sticky="w")

        self.button = customtkinter.CTkButton(self, text="Set Ground Settings", command=command)
        self.button.grid(pady=(5, 0))


class LabeledTextEntry(customtkinter.CTkFrame):
    """ A text entry widget with a label """

    def __init__(self, master, label_text="", placeholder_text="", **kwargs):
        super().__init__(master, **kwargs)

        self.label = customtkinter.CTkLabel(self, text=label_text, width=70, anchor="e")
        self.label.grid(row=0, column=0, padx=5)

        self.entry = customtkinter.CTkEntry(self, placeholder_text=placeholder_text)
        self.entry.grid(row=0, column=1)

    def get(self) -> str:
        return self.entry.get()

    def set(self, string: str):
        self.entry.delete(0, 'end')
        self.entry.insert(0, string)


def gps_loop(gps_port: str):
    try:
        gps_serial = serial.Serial(gps_port, 57600, timeout=1)
    except IOError as e:
        print(f"Failed to start GPS loop: {e}")
        return

    while True:
        new_data = gps_serial.readline().decode("utf-8").strip()

        new_crc, new_json = new_data.split(maxsplit=1)
        new_crc = int(new_crc)

        json_crc = crc32(new_json.encode("utf-8"))

        print(new_crc, json_crc)

        try:
            decoded_data = json.loads(new_json)
            global ROCKET_PACKET_CONT
            ROCKET_PACKET_CONT = decoded_data
            print(decoded_data)
        except IOError as e:
            print(f"Failed to decode json: {e}")



if __name__ == "__main__":
    t = Thread(target=gps_loop, args=["/dev/ttyUSB0"], name="gps_thread")
    t.start()

    app = App()

    # Catch Ctl + C
    signal.signal(signal.SIGINT, app.on_closing)

    app.start()
