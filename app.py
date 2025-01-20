from flask import Flask, render_template
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from urllib.request import urlopen, urlretrieve
import json
from watchdog.observers import Observer
from watchdog.events import PatternMatchingEventHandler
import os
from pathlib import Path
from queue import Queue
import time
import threading

import time

app = Flask(__name__)


class Handler(PatternMatchingEventHandler):
    def __init__(self, pattern=None):
        self.pattern = pattern or (".mp4")
        self.event_q = Queue()
        self.dummyThread = None


        # Set the patterns for PatternMatchingEventHandler
        PatternMatchingEventHandler.__init__(self, patterns=['*.mp4'],
                                        ignore_directories=True, case_sensitive=False)
        
    def on_any_event(self, event):
        if not event.is_directory and event.src_path.endswith(self.pattern):
            self.event_q.put((event, time.time()))
    
    def start(self):
        self.dummyThread = threading.Thread(target=self._process)
        self.dummyThread.daemon = True
        self.dummyThread.start()

    def _process(self):
        while True:
            time.sleep(1)
        
    def on_created(self, event):
        print("Watchdog received created event - % s." % event.src_path)
        # Event is created, you can process it now
        process_file(event.src_path)
 
    def on_modified(self, event):
        print("Watchdog received modified event - % s." % event.src_path)
        # Event is modified, you can process it now


@app.route('/')
def index():
    return render_template("index.html")


def download_meeting(site=None, type=None):
    if not site:
        site = "https://stream.jw.org/ts/BCJBRUbYKc"
    if not type:
        type = "Perhimpunan Tengah Pekan"
    
    options = webdriver.ChromeOptions()
    options.add_argument("headless")
    options.add_argument("--silent")
    driver = webdriver.Chrome(options=options)
    driver.get("https://stream.jw.org/ts/BCJBRUbYKc")
    time.sleep(5)

    html = driver.page_source
    # driver.quit()
    soup = BeautifulSoup(html, features="html.parser", from_encoding='utf-8')
    vods = soup.find_all("div", {"data-testid": "vod-program-card"}) 
    
    # Get available programs
    vods_options = []
    for v in vods:
        acara = v.find("p").get_text()
        tanggal = v.find("h6").get_text()

        # get link
        link = None
        button = driver.find_element(By.CSS_SELECTOR, "[data-testid='program-download-button']")
        button.click()
        download_720 = driver.find_element(By.CSS_SELECTOR, "[data-testid='program-download-option-720p']")
        download_720.click()



        vods_options.append({"vod": acara, "date": tanggal})

    # Get the downloadable links
    print(vods_options)
    driver.quit()

def process_file(file_name):
    print("Processing File")
    # get the file
    print("- Get File")
    # mp4box get the chapters
    print("- Get Chapters")
    # mp4box get the Harta part
    print("- Get Snippet")
    # display link to download
    print("- Display link to download")

if __name__ == "__main__":
    src_path = 'c:\\Users\\psubi\\Downloads'
    event_handler = Handler()
    observer = Observer()
    observer.schedule(event_handler, path=src_path, recursive=False)
    observer.start()
    download_meeting(site="https://stream.jw.org/ts/BCJBRUbYKc")
    app.run(debug=True)
