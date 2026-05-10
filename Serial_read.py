from serial.tools import list_ports
import serial, time
import pandas as pd
from datetime import datetime,timedelta
import os, re, platform
from plyer import notification
from win11toast import toast
import yagmail, asyncio
import telegram
from telegram import Bot
import configparser
import logging

config = configparser.ConfigParser()
config.read("config.ini")

# configure logging
logging.basicConfig(
    filename="log.log",        # log file name
    level=logging.INFO,        # log level
    format="%(asctime)s --> %(message)s",  # log format
    datefmt="%Y-%m-%d %H:%M:%S"
)

# Suppress noisy logs from libraries
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)

# ==== Variables ===== 
CHAT_ID = int(config["Telegram"]["chat_id"])
TOKEN = config["Telegram"]["token"]
reset_timer_flag = False # Flag for resetting timer in the main.py
receiver = config["Serial"]["email_receiver"]
app_password = config["Serial"]["app_password"]
# -------------------------

def process_data (raw_data,data_frequency,no_of_datasets):
    """
    Process raw sensor data in the format <temp,humi> into a timestamped pandas DataFrame.

    Args:
        raw_data (bytes): Incoming raw data in byte format.
                         Example: b"<30.0,75.0><29.9,76.0>...<30.1,74.5>\r\n"
                         where each pair represents <temperature,humidity>.
        data_frequency (int): Time interval (in seconds) between each data point.
        no_of_datasets (int): Number of data points expected.

    Returns:
        pd.DataFrame: A DataFrame with columns [Timestamp, Temperature, Humidity].
    """

    try:
        current_time = datetime.now()
        decoded_bytes = raw_data.decode("utf-8", errors="ignore").strip('\r\n')

        # removing brackets "< >"
        s_bytes_cleaned = decoded_bytes.replace("<", "")
        decoded_bytes = s_bytes_cleaned.split(">")
        
        # Convert each entry string into (temp, humi) tuple of floats
        parsed = [tuple(map(float, entry.split(','))) for entry in decoded_bytes if entry.strip()]

        # Reformat data into [temp, humi] format
        data = [ [temp, humi] for temp, humi in parsed ]

        # Calculate dataset time by backtracking from current time
        data_startTime = current_time - timedelta(seconds=no_of_datasets*data_frequency)
        timestamped_data = []
        x = 1   
        for temp, humi in data:
            data_time = data_startTime + timedelta(seconds=x*data_frequency)
            data_time = data_time.strftime("%Y-%m-%d %H:%M:%S")
            timestamped_data.append([data_time, temp, humi])
            x += 1
        return pd.DataFrame(timestamped_data,columns=["Timestamp","Temperature","Humidity"])

    except Exception as e:
        filename = os.path.abspath("error_log.txt")
        with open(filename, "a") as log_file:  # "a" means append mode
            log_file.write(f"{datetime.now().strftime("%Y-%m-%d %H:%M:%S")} --> Failed to decode raw data: {raw_data}\n")
        print(f"{datetime.now().strftime("%Y-%m-%d %H:%M:%S")} --> Decoding failed. Raw data have been saved to: {filename}")
        logging.error(f"Decoding failed. Raw data have been saved to: {filename}")
        return
    

def serial_read():
    config = configparser.ConfigParser()
    config.read("config.ini")

    # ==== Variables ===== 
    global reset_timer_flag
    arduino_port = config["Serial"]["port"] # arduino serial port
    data_frequency = int(config["Serial"]["data_frequency"]) # data sample frequency in seconds
    baud_rate = int(config["Serial"]["baud_rate"])  # baud rate of arduino serial
    numbers_of_datasets = int(config["Serial"]["numbers_of_datasets"]) # number of data received in single transmission
    # -------------------------

    print(f"{datetime.now().strftime("%Y-%m-%d %H:%M:%S")} --> serial_read() thread initialized with frequency = {data_frequency}, number_of_datasets = {numbers_of_datasets}")
    logging.info(f"serial_read() thread initialized with frequency = {data_frequency}, number_of_datasets = {numbers_of_datasets}")
    try:        
        serialCom = serial.Serial(arduino_port,baud_rate)
        
        # reset the arduino
        serialCom.setDTR(False)
        time.sleep(0.05)
        serialCom.setDTR(True)

        """
        # discard first 2 useless line (command sent to HC-12 transceiver for initialization)
        # You will see something like this in the terminal when arduino reset
        # 2025-09-01 16:40:52 --> b'AT+FU3AT+B9600OK+FU3\r\n'
        # 2025-09-01 16:40:52 --> b'OK+B9600\r\n'
        # If there is no OK+FU3 and OK+B9600 then we have problem on the receiver arduino (wrong COM, wiring issue or HC-12 transceiver setting issue)
        """
        s_bytes =  serialCom.readline() 
        print(f"{datetime.now().strftime("%Y-%m-%d %H:%M:%S")} --> {s_bytes}")
        logging.info(f"{s_bytes}")

        s_bytes =  serialCom.readline() 
        print(f"{datetime.now().strftime("%Y-%m-%d %H:%M:%S")} --> {s_bytes}")
        logging.info(f"{s_bytes}")
        notif_telegram("🟢 Serial_read() thread has been started.")

    except Exception as e:
        print(f"{datetime.now().strftime("%Y-%m-%d %H:%M:%S")} --> Failed to connect to the arduino: {e}")
        notif_desktop("🔴 Serial_read() thread has been terminated.", "Failed to connect to the arduino", 1)
        print(f"{datetime.now().strftime("%Y-%m-%d %H:%M:%S")} --> serial_read() thread has been terminated.")

        logging.error(f"Failed to connect to the arduino: {e}")
        logging.info(f"serial_read() thread has been terminated.")
        return
                
    while True:
        try:
            s_bytes =  serialCom.readline()   # Read one line of raw data from the serial port
            # print(f"{datetime.now().strftime("%Y-%m-%d %H:%M:%S")} --> Received raw data: {s_bytes}")

            # Case 1: Fire detection alert (print immediately but data is not saved)
            if (s_bytes.decode("utf-8", errors="ignore").strip('\r\n') == "Fire Detected"):
                s_bytes =  serialCom.readline() 
                decoded_bytes = s_bytes.decode("utf-8", errors="ignore").strip('\r\n')
                temp_str, humi_str = decoded_bytes.split(",")

                temp = float(temp_str)
                humi = float(humi_str)
                msg = (f"Potential Fire Detected! Please check immediately.\n" 
                + f"Temperature: {temp} \nHumidity: {humi}")
                notification_fire(msg)
                logging.info(f"Potential Fire Detected!")

            # Case 2: Test message from sensor node
            elif (s_bytes.decode("utf-8", errors="ignore").strip('\r\n') == "This is test code from sensor node."):
                print(f"{datetime.now().strftime("%Y-%m-%d %H:%M:%S")} --> {s_bytes}")
                logging.info(f"{s_bytes}")

            # Case 3: Normal <temp,humi> sensor readings, readings is saved into csv after running this
            else:
                data_df = process_data(s_bytes,data_frequency,numbers_of_datasets)
                
                # Extract date from "Timestamp" only
                data_df["Timestamp"] = pd.to_datetime(data_df["Timestamp"])
                data_df["Date"] = data_df["Timestamp"].dt.date

                # Rename and reformat time from "2025-08-26 02:39:26" to "02:39:26"
                data_df = data_df.rename(columns={"Timestamp": "Time"})
                data_df["Time"] = data_df["Time"].dt.strftime("%H:%M:%S")

                # Store data in files according to the date of each data
                for date, group in data_df.groupby("Date"):
                    os.makedirs("data_log", exist_ok=True)
                    filename = os.path.abspath(f"data_log/data_{date}.csv")
                    write_header = not os.path.exists(filename) # if file is already exist then = False
                    group = group.dropna()  # Drop rows with NaN values before saving
                    group.drop(columns="Date").to_csv(filename, index=False, header=write_header, mode="a")
                    print(f"{datetime.now().strftime("%Y-%m-%d %H:%M:%S")} --> Data saved to location: {filename} with {len(group)} rows")
                    logging.info(f"Data saved to location: {filename} with {len(group)} rows")
                    reset_timer_flag = True
            
        except TypeError as e:
            notif_desktop("⚠️ Failed to store readings. Reason: ", str(e), 5)
            notif_telegram("⚠️ Dashboard has failed to store readings.")
            print(f"{datetime.now().strftime("%Y-%m-%d %H:%M:%S")} --> serial_read() thread has encountered error: {e}")
            logging.info(f"serial_read() thread has encountered error: {e}")


        except Exception as e:
            notif_desktop("⚠️ Serial_read thread has crashed.", str(e), 1)
            notif_telegram(f"⚠️ Serial_read thread has crashed. Reason: {str(e)}")
            print(f"{datetime.now().strftime("%Y-%m-%d %H:%M:%S")} --> serial_read() thread has encountered error: {e}")
            logging.info(f"serial_read() thread has encountered error: {e}")
            break
    
    print(f"{datetime.now().strftime("%Y-%m-%d %H:%M:%S")} --> serial_read() thread has been terminated.")
    logging.error(f"serial_read() thread has been terminated.")
    notif_telegram("🔴 Serial_read() thread has been terminated.")
    config.serial_thread_status = "Not started"

def findall_csv():
    
    """
    -- Find all csv file with pattern of "YYYY-MM-DD" in the "data_log" folder 
    -- Returns a list of date strings extracted from the matching filenames.
    """
    folder_path = "./data_log" # Folder path containing all CSV files

    # Regex pattern to extract date (e.g., 2025-08-26)
    date_pattern = re.compile(r"\d{4}-\d{2}-\d{2}")

    # Set to store unique dates
    unique_dates = set()

    # Loop through files in the folder
    for filename in os.listdir(folder_path):
        if filename.endswith(".csv"):
            match = date_pattern.search(filename)
            if match:
                unique_dates.add(match.group())

    # Return result as list
    return sorted(list(unique_dates))

def notif_email(subject, body):
    global receiver, app_password

    yag = yagmail.SMTP(receiver, app_password)
    yag.send(
        to=receiver,
        subject=subject,
        contents=body
    )

def notif_desktop(title, message, type):
    system = platform.system()
    release = platform.release()
    notif_sound = os.path.abspath("notif.mp3")

    # run this if program is running on Windows 11 or Windows 10
    if (system == "Windows" and release in ["10", "11"]):
        toast(title, message, app_id="Sensor Node Dashboard", on_click=lambda args: None, audio = notif_sound)
    
    # run this for other systems
    else:
        notification.notify(
        title= title,
        message= message,
        app_name="Sensor Node Dashboard")

def notif_telegram(message):
    global TOKEN, CHAT_ID
    try:
        async def send_msg(msg):
            bot = Bot(token=TOKEN)
            await bot.send_message(chat_id=CHAT_ID, text=msg)
        
        asyncio.run(send_msg(message))
    except telegram.error.NetworkError as e:
        print(f"{datetime.now().strftime("%Y-%m-%d %H:%M:%S")} --> No internet connection. Notification is not sent to the Telegram.")
        logging.error(f"No internet connection. Notification is not sent to the Telegram.")


def notification_fire(message):
    title = "Fire Detected"
    notif_desktop(title, message, 1)
    notif_email(title, message)
    notif_telegram(message)
