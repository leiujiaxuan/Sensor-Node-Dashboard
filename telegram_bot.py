import configparser
import shutil
import os
import requests
import pandas as pd
import matplotlib
from matplotlib.dates import HourLocator, DateFormatter, num2date
import matplotlib.pyplot as plt
from datetime import datetime,timedelta
import telegram
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
from Serial_read import findall_csv
from time import sleep
import gc

config = configparser.ConfigParser()
config.read("config.ini")

# ==== Variables ===== 
try:
    CHAT_ID = config.getint("Telegram", "chat_id", fallback=0)
except ValueError:
    CHAT_ID = 0

TOKEN = config.get("Telegram", "token", fallback="").strip()
csv_folder_path = os.path.abspath("data_log")
plot_folder_path = os.path.abspath("plot")
csv_zip_path = os.path.abspath("data_log.zip")
plot_zip_path = os.path.abspath("plot.zip")

# ================
def saveall_plot():
    file_date = findall_csv() # find all csv files' "date"
    file_list = []
    os.makedirs("plot", exist_ok=True)
    
    # Make file list variable to store all csv files' path
    for i in range(len(file_date)):
        file_list.append(f"data_log/data_{file_date[i]}.csv")
    
    # Create a figure (without showing it)
    matplotlib.use("Agg")   # use non-GUI backend
    fig, ax = plt.subplots()

    for i in range(len(file_list)):
        data_df = pd.read_csv(file_list[i])
        data_df["Time"] = pd.to_datetime(data_df["Time"], format="%H:%M:%S")

        temp = data_df["Temperature"]
        humi = data_df["Humidity"]
        time = data_df["Time"]
        
        ax.clear() # clear previous plot
        ax.set_ylim(0, 100)
        ax.set_xlabel(file_date[i])
        ax.set_title("Temperature & Humidity Over 24 Hours")
        ax.grid(True, alpha=0.3)

        temp_line, = ax.plot(time, temp, label="Temperature (°C)", color="red", linewidth=2)
        humi_line, = ax.plot(time, humi, label="Humidity (%)", color="blue", linewidth=2)
        ax.legend()

        midnight = datetime.strptime("00:00:00", "%H:%M:%S")
        ax.set_xlim(midnight - timedelta(hours=0.5), midnight + timedelta(hours=24.5))
        ax.xaxis.set_major_locator(HourLocator(byhour=range(0, 25, 3)))
        ax.xaxis.set_major_formatter(DateFormatter('%H:%M'))

        # Save directly without showing
        fig.savefig(f"plot/plot_{file_date[i]}_both.png", dpi=300, bbox_inches="tight")

        temp_min, temp_max = min(temp_line.get_ydata()), max(temp_line.get_ydata())
        humi_min, humi_max = min(humi_line.get_ydata()), max(humi_line.get_ydata())
        temp_line.set_visible(True)
        humi_line.set_visible(False)

        ax.set_title("Temperature Over 24 Hours")
        ax.set_ylim(temp_min-0.5, temp_max+0.5)
        fig.savefig(f"plot/plot_{file_date[i]}_temponly.png", dpi=300, bbox_inches="tight")

        temp_line.set_visible(False)
        humi_line.set_visible(True)
        ax.set_title("Humidity Over 24 Hours")
        ax.set_ylim(humi_min-2, humi_max+2)
        fig.savefig(f"plot/plot_{file_date[i]}_humionly.png", dpi=300, bbox_inches="tight")

    # Clear all variables to prevent memory leak
    plt.close("all")
    locals().clear()
    gc.collect()

def zip_folder(folder_path, output_name):
    """Compress the folder specified by folder_path into a ZIP archive"""
    try:
        shutil.make_archive(
            output_name, 
            'zip',           # achive format
            root_dir=folder_path,
            base_dir="." # zip the entire folder in root_dir
            )   
        print(f'{datetime.now().strftime("%Y-%m-%d %H:%M:%S")} --> "{folder_path}" folder has successfully zipped.')
    except FileNotFoundError as e:
        print(f'{datetime.now().strftime("%Y-%m-%d %H:%M:%S")} --> Failed to zip folder. "{folder_path}" does not exist.')

def send_file(filepath):
    """Send the document located at filepath to the Telegram Bot"""
    global TOKEN, CHAT_ID
    url = f"https://api.telegram.org/bot{TOKEN}/sendDocument"
    
    try:
        with open(filepath, "rb") as file:
            requests.post(url, data={"chat_id": CHAT_ID}, files={"document": file})
        print(f'{datetime.now().strftime("%Y-%m-%d %H:%M:%S")} --> "{filepath}" has sent to the Telegram Bot.')
        return True

    except FileNotFoundError as e:
        print(f"{datetime.now().strftime("%Y-%m-%d %H:%M:%S")} --> Failed to send file. This file: {filepath} does not exist.")
        return False
    except requests.exceptions.ConnectionError:
        print(f"{datetime.now().strftime("%Y-%m-%d %H:%M:%S")} --> Failed to send file. No internet")
        return False
    except Exception as e:
        print(f"{datetime.now().strftime("%Y-%m-%d %H:%M:%S")} --> Failed to send file. Error: {e}")
        return False
    
async def getfile_csv(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global csv_folder_path, csv_zip_path
    await update.message.reply_text(f'Command received. Please wait for a while.')
    zip_folder(csv_folder_path,"data_log")

    result = send_file(csv_zip_path)
    if result == False:
        await update.message.reply_text( "⚠️ Sorry, I couldn't send the file.\n"
                "Possible reasons:\n"
                "\tFile does not exist.")

async def getfile_plot(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global plot_zip_path, plot_folder_path
    await update.message.reply_text(f'Command received. Please wait for a while.')
    saveall_plot()
    zip_folder(plot_folder_path,"plot")

    result = send_file(plot_zip_path)
    if result == False:
        await update.message.reply_text( "⚠️ Sorry, I couldn't send the file.\n"
        "Possible reasons:\n"
        "\tFile does not exist.")

def bot():
    # Build and run Telegram bot (best-effort). If token is invalid, disable the bot.
    if not TOKEN or CHAT_ID == 0:
        print(f'{datetime.now().strftime("%Y-%m-%d %H:%M:%S")} --> Telegram bot disabled (missing/invalid token or chat_id in config.ini).')
        return

    try:
        app = Application.builder().token(TOKEN).build()
        app.add_handler(CommandHandler("getfile_csv", getfile_csv))
        app.add_handler(CommandHandler("getfile_plot", getfile_plot))
        app.run_polling()

    except telegram.error.InvalidToken:
        print(f'{datetime.now().strftime("%Y-%m-%d %H:%M:%S")} --> Telegram bot disabled (invalid token).')
    except telegram.error.Unauthorized as e:
        print(f'{datetime.now().strftime("%Y-%m-%d %H:%M:%S")} --> Telegram bot stopped (unauthorized): {e}')
    except telegram.error.NetworkError as e:
        print(f'{datetime.now().strftime("%Y-%m-%d %H:%M:%S")} --> Telegram bot stopped (network error): {e}')
    except telegram.error.TelegramError as e:
        print(f'{datetime.now().strftime("%Y-%m-%d %H:%M:%S")} --> Telegram bot stopped (Telegram error): {e}')
    except Exception as e:
        print(f'{datetime.now().strftime("%Y-%m-%d %H:%M:%S")} --> Telegram bot crashed: {e}')