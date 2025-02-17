from flask import Flask, render_template, send_from_directory
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
import requests
import sys, os, subprocess as sp
import xml.etree.ElementTree as et
import shutil
from faster_whisper import WhisperModel
import math
import datetime
import locale

# global 
downloaded = False
startnow = False

# setup selenium
options = webdriver.ChromeOptions()
options.add_argument("headless")
options.add_argument("silent")
driver = webdriver.Chrome(options=options)

app = Flask(__name__)
app.config['OUTPUT_FOLDER'] = 'output'

class MyHandler(PatternMatchingEventHandler):
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
        if os.path.exists(event.src_path):
            process_file(event.src_path)

def extract_audio(input_video):
    print(f'[extract_audio] file : {input_video}')
    extracted_audio = f"audio-{input_video}.wav"
    command = f'mp4box -single 2 "{input_video}" -out "{extracted_audio}"'
    print(f'  > {command}')
    os.system(command)
    return extracted_audio

def transcribe(audio):
    print(f'[transcribe] use WhisperModel small : {audio}')
    model = WhisperModel("small")
    segments, info = model.transcribe(audio)
    language = info.language
    print("- transcription language", language)
    segments = list(segments)
    for segment in segments:
        print("#", end="")
    print('- completed')
    return language, segments

def format_time(seconds):
    hours = math.floor(seconds / 3600)
    seconds %= 3600
    minutes = math.floor(seconds / 60)
    seconds %= 60
    milliseconds = round((seconds - math.floor(seconds)) * 1000)
    seconds = math.floor(seconds)
    formatted_time = f"{hours:02d}:{minutes:02d}:{seconds:02d}.{milliseconds:03d}"
    return formatted_time

def format_current_week(language, source):
    # format Mon-Sun dates like this : 20–26 Januari
    locale.setlocale(locale.LC_TIME, "id_ID" if language=="id" else "en_US")
    today = datetime.datetime.today()
    today_num = datetime.datetime.today().weekday()
    
    start_of_week_date = today-datetime.timedelta(days=today_num)
    start_of_week_num = str.strip(datetime.datetime.strftime(start_of_week_date,"%e"))
    start_of_week_month = datetime.datetime.strftime(start_of_week_date,"%B")

    end_of_week_date = start_of_week_date+datetime.timedelta(days=6)   
    end_of_week_num = str.strip(datetime.datetime.strftime(start_of_week_date+datetime.timedelta(days=6), "%e"))
    end_of_week_month = datetime.datetime.strftime((today+datetime.timedelta(days=today_num)),"%B")

    value = ""
    test = "Perhimpunan Tengah Pekan_ 3–9 Februari_r720P - Harta Dalam Firman Allah.mp4"
    test_web = "February 17 – 23"
    if start_of_week_month == end_of_week_month:
        if source == "file":
            value = start_of_week_num+"–"+end_of_week_num+" "+end_of_week_month 
        else:
            if language == "id":
                value = start_of_week_num+"–"+end_of_week_num+" "+end_of_week_month 
            else:
                value = end_of_week_month + " " + start_of_week_num+" – "+end_of_week_num
    else:
        if source == "file":
            value = start_of_week_num+" "+start_of_week_month+" – "+end_of_week_num+" "+end_of_week_month
        else:
            if language == "id":
                value = start_of_week_num+" "+start_of_week_month+" – "+end_of_week_num+" "+end_of_week_month
            else:
                value = start_of_week_month + " " + start_of_week_num + " – "+ end_of_week_month+" "+end_of_week_num

    print(f'- current week : {value}') # 17–23 Februari / February 17 – 23
    return value

def format_current_week_title_id(english_title):
    month_num = 0
    month_num_2 = 0
    title_month_2_id = ""

    title_split = english_title.split()
    
    locale.setlocale(locale.LC_TIME, "en_US")
    month_num = datetime.datetime.strptime(title_split[0], "%B")
    
    if len(title_split) > 4:
        month_num_2 = datetime.datetime.strptime(title_split[3], "%B")

    # format title from this : January 20 – 26 to 20–26 Januari / January 27 - February 2 to 27 Januari - 2 Februari
    locale.setlocale(locale.LC_TIME, "id_ID")
    title_month_id = datetime.datetime.strftime(month_num, "%B")
    if len(title_split) > 4 and int(datetime.datetime.strftime(month_num_2,"%m")) > 0:
        title_month_2_id = datetime.datetime.strftime(month_num_2, "%B")

    if len(title_split) == 4:
        title_id = title_split[1]+title_split[2]+title_split[3]+" "+title_month_id
    else:
        title_id = title_split[1]+" "+title_month_2_id+" "+title_split[2]+" "+title_split[4]+" "+title_month_2_id

    value = title_id
    
    print(f'- title : {value}')
    return value

def get_all_mp4s():
    data=[]
    with os.scandir(path="./output") as entries:
        for entry in entries:
            if entry.is_file() and entry.name.endswith("mp4"):
                data.append({"file": entry.name, 
                             "link": f"./{entry.name}"})
    return data

@app.route('/')
def index():
    data=get_all_mp4s()

    return render_template("index.html", data = data)

@app.route('/download/<path:filename>')
def download(filename):
    full_path = os.path.join(app.root_path, app.config['OUTPUT_FOLDER'])
    return send_from_directory(full_path, filename)

def get_chapters(inp):
    print('[get_chapters] Split files into chapters')
    # result=sp.run(["ffprobe", "-v", "16", "-show_chapters", "-of", "json", inp],
    #     stdout=sp.PIPE,
    #     stderr=sp.STDOUT)
    chapter_file = f'chapters_{inp}.xml'
    
    print(f'- dump to {chapter_file}')
    result = sp.run(["MP4Box", "-dump-chap", inp, "-out", chapter_file],
        stdout=sp.PIPE,
        stderr=sp.STDOUT)
    
    chapters_new = []
    
    chapters = {}
    chapter = None
    next_chapter = None
    if result.returncode == 0 and "No chapters" not in str(result.stdout):
        print(f'- parsing {chapter_file}')
        tree = et.parse(chapter_file)
        root = tree.getroot()
        chapters = root.findall('TextSample')
        for chapter in chapters:
            index = chapters.index(chapter)
            if index < len(chapters)-1:
                next_chapter = chapters[index + 1]
            else:
                next_chapter = None

            if chapter is not None:
                fno=os.path.splitext(os.path.basename(inp))[0]
                ext=os.path.splitext(inp)[1]
                out=f'./{fno} - {chapter.text}{ext}'
                print(f'- File Name : {out}')
                start_time = chapter.attrib.get("sampleTime")
                if next_chapter is not None:
                    end_time = next_chapter.attrib.get("sampleTime")
                else:
                    end_time = ''

                chapters_new.append({
                    "title": chapter.text,
                    "start_time": chapter.attrib.get("sampleTime"),
                    "end_time": end_time
                })

                #os.system(f'ffmpeg -ss {start_time} -to {end_time} -i "{inp}" -map 0 -c copy "{out}" -v 16')        
                command = f'mp4box -splitx {start_time}-{end_time} "{inp}" -out "{out}"'
                print(f'  > {command}')
                os.system(command)

                # Also fix the chapter
                print(f'- fix chapter')
                new_chapter_file = f"{chapter.text}.txt"
                lines = ["CHAPTER1=00:00:00.000\n",
                         "CHAPTER1NAME=Bagian1\n",
                         f"CHAPTER2={end_time}\n",
                         "CHAPTER2NAME=End"]
                with open(new_chapter_file, 'w') as c:
                    c.writelines(lines)
                command = f'mp4box -chap "{new_chapter_file}" "{out}"'
                print(f'  > {command}')
                os.system(command)
                print(f'- cleanup')
                os.remove(new_chapter_file)
    
    os.remove(chapter_file)
    
    return chapters_new

def download_meeting(site=None, type=None):
    print(f"[download_meeting] Get Selenium to download : {type}")
    if not site:
        site = "https://stream.jw.org/ts/BCJBRUbYKc"
    if not type:
        type = "Perhimpunan Tengah Pekan"
    
    print(f"- opening page : {site}")
    driver.get(site)
    time.sleep(5)

    html = driver.page_source
    # driver.quit()
    # soup = BeautifulSoup(html, features="html.parser", from_encoding='utf-8')
    # vods = soup.find_all("div", {"data-testid": "vod-program-card"}) 
    
    # Get list of files we have
    data=get_all_mp4s()

    # download file
    print('- find Video on Demands')
    vods = driver.find_elements(By.CSS_SELECTOR, "[data-testid='vod-program-card']")
    for vod in vods:
        title = vod.find_element(By.CSS_SELECTOR, "[data-testid='vod-program-card-overline']")
        
        if title.text != type:
            continue
        
        program_date = vod.find_element(By.CSS_SELECTOR, "[data-testid='vod-program-card-title']")

        # if file is already downloaded, no need to
        program_date_id = format_current_week_title_id(program_date.text)
        file_list = [p['file'] for p in data if program_date_id in p['file']]
        if len(file_list) > 0:
            print('- File Found, no need to download')
            global downloaded
            downloaded = True
            return
        
        # also remove previous week files
        file_list = [p['file'] for p in data if not program_date_id in p['file']]
        if len(file_list) > 0:
            for f in file_list:
                print(f"- removing old file {f}")
                os.remove("output\\"+f)

        look_for_this_program_date = format_current_week("en", "web")
        if title.text == type and program_date.text == look_for_this_program_date :
            print(f'- found : {type} for {look_for_this_program_date}')
            button = vod.find_element(By.CSS_SELECTOR, "[data-testid='program-download-button']")
            print('- click Download button')
            button.click()
            download_720 = driver.find_element(By.CSS_SELECTOR, "[data-testid='program-download-option-720p']")
            print('- click Download 720 button')
            download_720.click()
            print('- waiting for download to complete ...')
        else:
            print(f'- VOD not available yet : {type} for {look_for_this_program_date}')

def process_file(file_name):
    print(f"[process_file] Download Completed : {file_name}")
    # get the files to local folder
    source = file_name
    destination = os.path.basename(file_name)
    print(f"- Move from {source} to {destination}")
    shutil.move(source, destination)
    
    global downloaded
    downloaded = True
    # mp4box get the chapters
    print(f"- Retrieve Chapters")
    ptp_chapters = get_chapters(os.path.basename(file_name))

    harta_start_time = ""
    harta_end_time = ""

    index = next((i for i, d in enumerate(ptp_chapters) if 'Harta' in d.get('title')), None)
    if index is not None:
        harta_start_time = ptp_chapters[index].get('start_time')
        harta_end_time = ptp_chapters[index].get('end_time')
        print(f'- start/end : {harta_start_time} to {harta_end_time}')

    # compare with the audio
    print(f'- compare with transcription from audio')
    harta_video_file_name = f"Perhimpunan Tengah Pekan_ {format_current_week('id', 'file')}_r720P - Harta Dalam Firman Allah.mp4"
    if os.path.exists(harta_video_file_name):
        print(f'- attempting to extract audio {harta_video_file_name}')
        audio_file_name = extract_audio(harta_video_file_name)
        print(f'- attempting to transcribe {harta_video_file_name}')
        language, segments = transcribe(audio=audio_file_name)
        for segment in segments:
            if segment.text.lower().find("harta dalam firman") > 0:
                new_time = format_time(segment.start)
                if harta_start_time < new_time:
                    harta_start_time = new_time
                    print(f'- found start time : {harta_start_time}')
            if segment.text.lower().find("permata rohani") > 0:
                new_time = format_time(segment.start)
                if harta_end_time > new_time:
                    harta_end_time = new_time
                    print(f'- found end time : {harta_end_time}')
                    break
        if harta_end_time > "00:12:00.000" or harta_end_time == "":
            harta_end_time = "00:12:00.000"
        os.remove(audio_file_name)

    if len(harta_end_time) > 0:
        # cut the Harta video to just the first part
        harta_video_file_name2 = "10_" + harta_video_file_name
        print(f'- extracting harta video : {harta_video_file_name2}')
        command = f'mp4box -splitx {"00:00:00.000"}-{harta_end_time} "{harta_video_file_name}" -out "{harta_video_file_name2}"'
        print(f'  > {command}')
        os.system(command)

        # Also fix the chapter
        print(f'- fix chapter')
        new_chapter_file = f"chapter10.txt"
        lines = ["CHAPTER1=00:00:00.000\n",
                "CHAPTER1NAME=Bagian1\n",
                f"CHAPTER2={harta_end_time}\n",
                "CHAPTER2NAME=End"]
        with open(new_chapter_file, 'w') as c:
            c.writelines(lines)
        command = f'mp4box -chap "{new_chapter_file}" "{harta_video_file_name2}"'
        print(f'  > {command}')
        os.system(command)
        print(f'- cleanup')
        os.remove(new_chapter_file)

        print(f"- Move to output")
        if not os.path.exists(harta_video_file_name2):
            shutil.move(harta_video_file_name2, "output/" + harta_video_file_name2)

        remaining_files = [f for f in os.listdir() if f.endswith("mp4")]
        for f in remaining_files:
            print(f"Remove: {f}")
            os.remove(f)

    print("- Display link to download")

def run_watcher(path='c:\\Users\\psubi\\Downloads'):
    handler = MyHandler()

    observer = Observer()
    observer.schedule(handler, path)
    observer.start()
    try:
        while True:
            time.sleep(1)
            pass
    except KeyboardInterrupt:
        observer.stop()
    observer.join

def check_recording_availability():
    result = requests.get("https://psubianto.pythonanywhere.com/getcode")
    stream_code = json.loads(result.content).get("code")
    default_site = f"https://stream.jw.org/ts/{stream_code}"

    if startnow or datetime.datetime.now().weekday() in [0,1,5,6]:
        if startnow or datetime.datetime.now().time() > datetime.time(12,0,0):
            # if it's past 12pm EST in US, on Monday, Tuesday, Saturday, Sunday
            if startnow or not downloaded:
                download_meeting(site=default_site, type='MIDWEEK MEETING')
            else:
                print("Meeting file is already downloaded")
        else:
            print("Will download after 12p")
    else:
        print("Download is only on Monday/Tuesday Saturday/Sunday")
    time.sleep(3600*4) # check every 4 hours

if __name__ == "__main__":
    if len(sys.argv)>1:
        startnow = sys.argv[1] == '--startnow'
    else:
        startnow = True
    print('startnow' if startnow else 'start later')
    
    if not os.path.exists('output'):
        print('output folder created')
        os.makedirs('output')

    # Start watchdog to wait for finished download
    watcher_thread = threading.Thread(target=run_watcher)
    watcher_thread.daemon = True
    watcher_thread.start()
    
    # Also Monday evening and Saturday evening check for recording
    jw_stream_thread = threading.Thread(target=check_recording_availability)
    jw_stream_thread.daemon = True
    jw_stream_thread.start()
    
    app.run(debug=False)
    # process_file("Perhimpunan Tengah Pekan_ 20–26 Januari_r720P.mp4")
    print("Finished")
