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
from time import sleep
import json

## LOCAL IMPORTS ##
from utils import GPSPoint

# Spaceport: 32.940058, -106.921903
DEFAULT_LAT = 40.82320
DEFAULT_LON = -96.69693

# global ROCKET_PACKET_CONT 
ROCKET_PACKET_CONT = None

class App(customtkinter.CTk):

    APP_NAME = "UNL Aerospace Telemetry Tracker"
    WIDTH = 1024
    HEIGHT = 768

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.serialport = None

        self.title(App.APP_NAME)
        self.geometry(str(App.WIDTH) + "x" + str(App.HEIGHT))
        self.minsize(App.WIDTH, App.HEIGHT)

        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        # The ground station position
        self.ground_marker: Optional[Any] = None
        self.ground_position = GPSPoint(0, 0, 0)

        # Rocket position
        self.air_marker: Optional[Any] = None
        self.air_position = GPSPoint(0, 0, 0)

        # ============ create two CTkFrames ============

        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.frame_left = customtkinter.CTkFrame(master=self, width=250, corner_radius=0, fg_color=None)
        self.frame_left.grid(row=0, column=0, padx=0, pady=0, sticky="nsew")
        self.frame_left.grid_propagate(False)

        self.frame_right = customtkinter.CTkFrame(master=self, corner_radius=0)
        self.frame_right.grid(row=0, column=1, rowspan=1, pady=0, padx=0, sticky="nsew")

        # ============ frame_left ============

        #self.frame_left.grid_rowconfigure(5, weight=1)

        #self.button_1 = customtkinter.CTkButton(master=self.frame_left, text="Set Marker", command=self.set_marker_event)
        #self.button_1.grid(pady=(20, 0), padx=(20, 20), row=0, column=0)

        telemetry_frame = customtkinter.CTkFrame(self.frame_left, fg_color="transparent", width=250)
        telemetry_frame.grid_propagate(False)
        telemetry_frame.grid(pady=(20, 0), padx=(10, 0))

        PADDING = 15
        customtkinter.CTkLabel(telemetry_frame, text="Latitude:", font=("Arial", 18)).grid(row=0, column=0, sticky="e", padx=(0, PADDING))
        self.telemetry_lat = customtkinter.CTkLabel(telemetry_frame, text="p", font=("Arial", 18), compound="right", justify="right", anchor="e")
        self.telemetry_lat.grid(row=0, column=1, sticky="e")
        customtkinter.CTkLabel(telemetry_frame, text="Longitude:", font=("Arial", 18)).grid(row=1, column=0, sticky="e", padx=(0, PADDING))
        self.telemetry_lon = customtkinter.CTkLabel(telemetry_frame, text="x", font=("Arial", 18), compound="right", justify="right", anchor="e")
        self.telemetry_lon.grid(row=1, column=1, sticky="e")
        customtkinter.CTkLabel(telemetry_frame, text="Altitude:", font=("Arial", 18)).grid(row=2, column=0, sticky="e", padx=(0, PADDING))
        self.telemetry_alt = customtkinter.CTkLabel(telemetry_frame, text="z", font=("Arial", 18), compound="right", justify="right", anchor="e")
        self.telemetry_alt.grid(row=2, column=1, sticky="e")
        customtkinter.CTkLabel(telemetry_frame, text="Elevation:", font=("Arial", 18)).grid(row=3, column=0, sticky="e", padx=(0, PADDING))
        self.telemetry_elev = customtkinter.CTkLabel(telemetry_frame, text="z", font=("Arial", 18), compound="right", justify="right", anchor="e")
        self.telemetry_elev.grid(row=3, column=1, sticky="e")
        customtkinter.CTkLabel(telemetry_frame, text="Bearing:", font=("Arial", 18)).grid(row=4, column=0, sticky="e", padx=(0, PADDING))
        self.telemetry_bear = customtkinter.CTkLabel(telemetry_frame, text="z", font=("Arial", 18), compound="right", justify="right", anchor="e")
        self.telemetry_bear.grid(row=4, column=1, sticky="e")


        self.map_label = customtkinter.CTkLabel(self.frame_left, text="Map Style:", anchor="w")
        self.map_label.grid(padx=(20, 20), pady=(20, 0))
        self.map_option_menu = customtkinter.CTkOptionMenu(self.frame_left, values=["Google hybrid", "Google normal", "Google satellite"], command=self.change_map)
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
        self.map_widget.add_right_click_menu_command(label="Set Ground Position", command=self.set_ground_position, pass_coords=True)

        # self.map_widget.add_left_click_map_command(self.set_air_position)

        # Set default value
        self.map_widget.set_position(DEFAULT_LAT, DEFAULT_LON)
        self.map_widget.set_zoom(16)
        self.map_option_menu.set("Google hybrid")
        self.map_widget.set_tile_server("https://mt0.google.com/vt/lyrs=y&hl=en&x={x}&y={y}&z={z}&s=Ga", max_zoom=22)

    def set_air_position(self):

        print("function ran yay")
        if ROCKET_PACKET_CONT is None:
            self.after(500, self.set_air_position)
            return

        self.telemetry_lat.configure(text=f"{ROCKET_PACKET_CONT["latitude"]:.8f}")
        self.telemetry_lon.configure(text=f"{ROCKET_PACKET_CONT["longitude"]:.8f}")
        self.telemetry_alt.configure(text=f"{ROCKET_PACKET_CONT["altitude"]:.2f}m")

        self.air_position = GPSPoint(
            ROCKET_PACKET_CONT["latitude"],
            ROCKET_PACKET_CONT["longitude"],
            ROCKET_PACKET_CONT["altitude"]
        )

        last_marker = self.air_marker

        self.air_marker = self.map_widget.set_marker(ROCKET_PACKET_CONT["latitude"], ROCKET_PACKET_CONT["longitude"])

        if last_marker is not None:
            last_marker.delete()

        if self.ground_position is None:
            self.after(500, self.set_air_position)
            return

        # Straight line distance between the ground positions
        #distance = self.ground_position.distance_to(self.air_position)

        # Altitude above ground station position
        altitude = self.ground_position.altitude_to(self.air_position)
        if altitude is None:
            altitude = 0.0

        horiz = self.ground_position.bearing_mag_corrected_to(self.air_position)
        vert = self.ground_position.elevation_to(self.air_position)

        self.telemetry_bear.configure(text=f"{horiz:.2f}°")
        self.telemetry_elev.configure(text=f"{vert:.2f}°")

        self.after(500, self.set_air_position)

    def set_ground_position(self, coords):
        if self.ground_marker is not None:
            self.ground_marker.delete()

        self.ground_position = GPSPoint(coords[0], coords[1], 1381)
        self.ground_marker = self.map_widget.set_marker(coords[0], coords[1])

    def change_map(self, new_map: str):
        if new_map == "Google hybrid":
            self.map_widget.set_tile_server("https://mt0.google.com/vt/lyrs=y&hl=en&x={x}&y={y}&z={z}&s=Ga", max_zoom=22)
        elif new_map == "Google normal":
            self.map_widget.set_tile_server("https://mt0.google.com/vt/lyrs=m&hl=en&x={x}&y={y}&z={z}&s=Ga", max_zoom=22)
        elif new_map == "Google satellite":
            self.map_widget.set_tile_server("https://mt0.google.com/vt/lyrs=s&hl=en&x={x}&y={y}&z={z}&s=Ga", max_zoom=22)

    def on_closing(self, event=0):
        self.destroy()

    def start(self):
        self.after(500, self.set_air_position)

        self.mainloop()


def gps_loop():
    gps_serial = serial.Serial('/dev/ttyUSB0', 57600, timeout=1)

    while True:
        new_data = gps_serial.readline().decode("utf-8").strip()
        # print(new_data)
        try:
            new_new_data = json.loads(new_data)
            # print(new_data)
            global ROCKET_PACKET_CONT
            ROCKET_PACKET_CONT = new_new_data
            # print(ROCKET_PACKET_CONT["latitude"])
        except:
            print("Failed to decode json")
        

if __name__ == "__main__":
    t = Thread(target=gps_loop)
    t.start()

    app = App()
    app.start()
