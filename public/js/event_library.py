from yvrc_addons.dbus_introspection import send_dbus_msg, wait_for_dbus_msg
from yvrc_addons.dbus_introspection.types import DBusArray, DBusUint32
import stb_ssh_core
from stb_ssh_core import send_dbus_message
from datetime import datetime
import pytz
from enum import Enum
from tabulate import tabulate
import time
import json
import os.path
import shutil


dirNameExposed = "dvr-soak-contents/"

def create_folder():
    if not os.path.exists(dirNameExposed):
        os.mkdir(dirNameExposed)

def save_recordings(recordings, file_name=dirNameExposed+"dvr-soak-recordings.json"):
    create_folder()
    with open(file_name, 'w') as f:
        json.dump(recordings, f)

def load_recordings(file_name=dirNameExposed+"dvr-soak-recordings.json"):
    create_folder()
    with open(file_name, 'r') as json_file:
        return json.load(json_file)

def load_sleep_time(file_name=dirNameExposed+"dvr-soak-sleep.json"):
    create_folder()
    object_saved = {}
    with open(file_name, 'r') as json_file:
        object_saved = json.load(json_file)
    if "sleep_time" in object_saved.keys():
        return object_saved["sleep_time"]
    else:
        return 0


def save_sleep_time(sleep_time, file_name=dirNameExposed+"dvr-soak-sleep.json"):
    create_folder()
    with open(file_name, 'w') as f:
        json.dump({
            "sleep_time" : sleep_time
        }, f)

def create_snapshot(list, block_order, full_list=None, failed_recordings=None, file_name=dirNameExposed+"dvr-soak-log.json"):
    create_folder()
    current_snapshots = []
    if not os.path.isfile(file_name):
        with open(file_name, 'w') as f:
            json.dump([], f)
    else:
        try:
            with open(file_name, 'r') as json_file:
                current_snapshots = json.load(json_file)
        except ValueError:
            current_snapshots=[]
    current_snapshots.append({
        "time":time.time(),
        "list":list,
        "full_list" : full_list,
        "failed_list" : failed_recordings,
        "blocks":block_order
    })
    with open(file_name, 'w') as f:
        json.dump(current_snapshots, f, cls=BlockTypeEncoder)

def rollback_from_snapshot():
    pass

def check_recordings(recordings):
    start = 0
    end = 100
    not_seen_all_media_records = True
    while not_seen_all_media_records:
        list_records = get_local_media_records(start, end)["mediaRecords"]
        if len(list_records) == 100:
            not_seen_all_media_records = True
            start = start + 100
            end = end + 100
        else:
            not_seen_all_media_records = False
        for recording in recordings:
            for media_record in list_records:
                if str(media_record["identifiers"][0]["value"][0]) == str(recording["event"]["eventLocator"]):
                    if media_record["acquisitionStatus"] == "ACQUIRED":
                        recording["done"] = True
    failed = []
    for recording in recordings:
        if not recording["done"]:
            failed.append(recording)
    return failed

def get_sleep_time(recordings):
    last_recording = 0
    for recording in recordings:
        recording_finish = (recording["event"]["start"]
            + recording["event"]["publishedDuration"]
        )
        if recording_finish > last_recording:
            last_recording = recording_finish
    return last_recording - time.time()

def record_all_in_list(list):
    recordings = []
    for event in list["events"]:
        booking = book_recording(event["eventLocator"])["result"]
        print(booking)
        if booking["status"] == "SUCCESS":
            recordings.append({
                "booking" : booking,
                "event" : event,
                "done" : False
            })
    return recordings

def get_local_media_records(from_index, to_index):
    return send_dbus_msg(
    "Zinc.LocalMediaLibrary",
    "/Zinc/Media/LocalMediaLibrary2",
    "Zinc.Media.LocalMediaLibrary2.getMediaRecords",
    2,
    0,
    True,
    DBusUint32(from_index),
    DBusUint32(to_index)
)

def delete_all_bookings():
    try:
        for booking in get_booked_recordings()['scheduledRecordings']:
            if booking["publishedStartTime"] > time.time():
                delete_booking(booking["bookingReference"])
    except CalledProcessError as e:
            pass
def stop_all_recordings():
    try:
        for booking in get_booked_recordings()['scheduledRecordings']:
            if booking["publishedStartTime"] < time.time():
                delete_in_progress_recording(booking["eventLocator"])
    except CalledProcessError as e:
            pass

def book_recording(service_locator):
    return send_dbus_msg(
    "Zinc.ContentAcquisition",
    "/Zinc/ContentAcquisition/LinearAcquisition2",
    "Zinc.ContentAcquisition.LinearAcquisition2.bookEvent",
    service_locator,
    DBusUint32(1)
)

def delete_booking(service_locator):
    return send_dbus_msg(
    "Zinc.ContentAcquisition",
    "/Zinc/ContentAcquisition/LinearAcquisition2",
    "Zinc.ContentAcquisition.LinearAcquisition2.deleteBooking",
    service_locator
)
def delete_in_progress_recording(service_locator):
    return send_dbus_msg(
    "Zinc.ContentAcquisition",
    "/Zinc/ContentAcquisition/LinearAcquisition2",
    "Zinc.ContentAcquisition.LinearAcquisition2.stopInProgressRecording",
    str(service_locator),
    False

)
def get_events(service, from_time, to_time):
    return send_dbus_msg(
    "Zinc.Metadata",
    "/Zinc/Metadata/EventRepository",
    "Zinc.Metadata.EventRepository.getScheduleEvents",
    DBusArray([service]),
    DBusUint32(from_time),
    DBusUint32(to_time)
)

def get_services_list():
    return send_dbus_msg(
    "Zinc.Metadata",
    "/Zinc/Metadata/ServiceRepository",
    "Zinc.Metadata.ServiceRepository.getServiceList"
)

def get_booked_recordings():
        return send_dbus_msg(
        "Zinc.ContentAcquisition",
        "/Zinc/ContentAcquisition/LinearAcquisition2",
        "Zinc.ContentAcquisition.LinearAcquisition2.getScheduledRecordings"
)

class EventBlockTypes(Enum):
    Back_To_Back = "back_to_back",
    Step = "step",
    Skip = "skip",
    Concurrent = "concurrent",
    ShortestEvent = "shortest_event",
    NextEvent = "next_event"

PUBLIC_ENUMS = {
    'EventBlockTypes': EventBlockTypes,
}
class BlockTypeEncoder(json.JSONEncoder):
    def default(self, obj):
        if type(obj) in PUBLIC_ENUMS.values():
            return {"__enum__": str(obj)}
        return json.JSONEncoder.default(self, obj)

class EventSort:
    def __init__(self, from_time, to_time, channels_list=None, **kwargs):
        sort_by_channel_size = kwargs.get('sort_by_channel_size', True)
        self.events = {
            "channels":[],
            "events":[]
        }
        self.channels = []
        if not channels_list:
            channels_list = get_services_list()["serviceLocators"]
        for service in channels_list:
            self.channels.append(service)
            for event in get_events(service, from_time, to_time)["events"]:
                self.events["events"].append(event)
                found_previous_channel = False
                for events_channel in self.events["channels"]:
                    if events_channel["service"] == service:
                        events_channel["events"].append(event)
                        events_channel["occurence"] = (
                            events_channel["occurence"] + 1
                        )
                        found_previous_channel = True
                if not found_previous_channel:
                    self.events["channels"].append({
                        "service":str(service),
                        "events":[event],
                        "occurence": 1
                    })
            if sort_by_channel_size:
                self.events["channels"].sort(key=lambda x: x["occurence"],
                    reverse=True
                )

    def create_recording_mux(self,start, *blocks):
        master_block = {
            "start":start,
            "events":[],
            "tuners_needed":1
        }
        for block in blocks:
            events_suggested = []
            if block == EventBlockTypes.Back_To_Back:
                events_suggested = self.create_back_to_back(master_block)
            if block == EventBlockTypes.Skip:
                events_suggested = self.create_skip(master_block)
            if block == EventBlockTypes.Step:
                events_suggested = self.create_step(master_block)
            if block == EventBlockTypes.Concurrent:
                events_suggested = self.create_concurrent(2, master_block)
                master_block["tuners_needed"] = 2
            if block == EventBlockTypes.ShortestEvent:
                events_suggested = self.find_shortest(master_block)
            if block == EventBlockTypes.NextEvent:
                events_suggested = self.next_event(master_block)
            for event in events_suggested:
                master_block["events"].append(event)
                master_block["start"] = (event["start"]
                    + event["publishedDuration"]
                )
        return master_block
    def get_full_list(self):
        return self.events
    def next_event(self, prev_block=None):
        if prev_block:
            block_start = prev_block["start"]
        else:
            block_start = 0
        block_recordings = []
        shortest_duration = None
        for channel in self.events["channels"]:
            for event_a in channel["events"]:
                if event_a["start"]>=block_start:
                    block_recordings.append(event_a)
                    return block_recordings
        return block_recordings

    def find_shortest(self, prev_block=None):
        if prev_block:
            block_start = prev_block["start"]
        else:
            block_start = 0
        block_recordings = []
        shortest_duration = None
        for channel in self.events["channels"]:
            for event_a in channel["events"]:
                if event_a["start"]>=block_start:
                    if shortest_duration is None:
                        shortest_duration = event_a
                    else:
                        if (int(event_a["publishedDuration"]) <
                            int(shortest_duration["publishedDuration"])):
                            shortest_duration = event_a
        if not shortest_duration is None:
            block_recordings.append(shortest_duration)
        return block_recordings

    def create_back_to_back(self, prev_block=None, **options):
        quantity = 2
        if prev_block:
            block_start = prev_block["start"]
        else:
            block_start = 0
        block_recordings = []
        for channel in self.events["channels"]:
            for event_i in range(len(channel["events"])):
                if (event_i < range(len(channel["events"]))[-1] and
                    len(block_recordings) != quantity):
                    #check back to create
                    if channel["events"][event_i]["start"] >= block_start:
                        current_stop = (channel["events"][event_i]["start"]
                            + channel["events"][event_i]["publishedDuration"])
                        next_start = channel["events"][event_i+1]["start"]
                        if current_stop==next_start:
                            if not channel["events"][event_i] in block_recordings:
                                block_recordings.append(channel["events"][event_i])
                            block_recordings.append(channel["events"][event_i+1])
        return block_recordings

    def create_skip(self,prev_block=None, **options):
        if prev_block:
            block_start = prev_block["start"]
        else:
            block_start = 0
        block_recordings = []
        for channel in self.events["channels"]:
            for event_a in channel["events"]:
                if event_a["start"]>=block_start:
                    for event_b in channel["events"]:
                        event_a_stop = (event_a["start"]
                            + event_a["publishedDuration"])
                        event_b_start = event_b["start"]
                        if event_a_stop < event_b_start:
                            block_recordings.append(event_a)
                            block_recordings.append(event_b)
                            return block_recordings
        return block_recordings

    def create_step(self, prev_block=None):
        if prev_block:
            block_start = prev_block["start"]
        else:
            block_start = 0
        block_recordings = []
        for channel_a in self.events["channels"]:
            for event_i_a in range(len(channel_a["events"])):
                event_a = channel_a["events"][event_i_a]
                for channel_b in self.events["channels"]:
                    for event_i_b in range(len(channel_b["events"])):
                        event_b = channel_b["events"][event_i_b]
                        if event_a["start"]>=block_start:
                            if channel_a["service"] !=  channel_b["service"]:
                                event_a_stop = (event_a["start"]
                                    + event_a["publishedDuration"])
                                event_b_start = event_b["start"]
                                if event_a_stop == event_b_start:
                                    block_recordings.append(event_a)
                                    block_recordings.append(event_b)
                                    return block_recordings
        return block_recordings

    def sort(**kwargs):
        shortest_first = kwargs.get('shortest_first', True)

    def create_concurrent(self, ammount, prev_block=None):
        if prev_block:
            block_start = prev_block["start"]
        else:
            block_start = 0
        block_recordings = []
        for channel_a in self.events["channels"]:
            for event_i_a in range(len(channel_a["events"])):
                event_a = channel_a["events"][event_i_a]
                if event_a["start"]>=block_start:
                    block_recordings = []
                    block_recordings.append(event_a)
                    global_start_time = event_a["start"]
                    for channel_b in self.events["channels"]:
                        for event_i_b in range(len(channel_b["events"])):
                            event_b = channel_b["events"][event_i_b]
                            if channel_a["service"] !=  channel_b["service"]:
                                if event_b["start"] == global_start_time:
                                    block_recordings.append(event_b)
                                    if len(block_recordings) == ammount:
                                        return block_recordings

        return block_recordings
