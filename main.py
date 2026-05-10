from customtkinter import *
from tkinter import ttk
from PIL import Image
import threading
from Serial_read import *
import Serial_read
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.dates import HourLocator, DateFormatter, num2date
import mplcursors
import matplotlib.pyplot as plt
import os
import configparser
import multiprocessing
import telegram_bot

os.makedirs("data_log", exist_ok=True) # Create data_log folder if it does not exist

# ==== Variables ===== 
sel_txtcolor = "#2A8C55"
sel_hovercolor = "#eee"
sel_fgcolor = "#FFF"
unsel_txtcolor = "#FFF"
unsel_fgcolor = "transparent"
unsel_hovercolor = "#207244"
dropdown_combobox = None
canvas = None
thread_label = None
info_frame2 = None
toolbar = None
button_frame = None
temp_line = None
humi_line = None
t = threading.Thread(target=serial_read, daemon=True) # thread for reading from arduino
bot_process = multiprocessing.Process(target=telegram_bot.bot, daemon=True) # Telegram bot process
switch_plot_btn = None
mode = "both"
cursor = None
data_folder = os.path.abspath("data_log")
df = []
available_dates = None
selected_dates = findall_csv()
treeview_initialize = False
file_time = findall_csv()
timer_duration = 3800  # in seconds
end_time = None
running = False   # flag to track timer status

# -------------------------
def show_date_dropdown(dates):
    global dropdown_combobox, cursor
    def combobox_callback(choosen_date):
        if cursor is not None:
            cursor.remove()  # removes all annotations in the graph when switching date

        filename = f"data_log/data_{choosen_date}.csv"
        plot_graph(filename)

    # Destroy combobox if already existed
    if dropdown_combobox:
        dropdown_combobox.destroy()

    # Dropdown box for choosing date
    dropdown_combobox = CTkComboBox(button_frame, values=sorted(dates), command=combobox_callback)
    dropdown_combobox.pack(pady=15)
    
    if dates == []:
        dropdown_combobox.set("No available files.")
    else:
        dropdown_combobox.set(sorted(dates)[-1]) # choose the latest date'
        if cursor is not None:
            cursor.remove()  # removes all annotations created by this cursor
        combobox_callback(sorted(dates)[-1]) # choose the latest date'

def plot_graph(filename):
    global canvas, toolbar, fig, ax, temp_line, humi_line, cursor
    data_df = pd.read_csv(filename)

    # Convert 'Time' column from string (HH:MM:SS) to pandas datetime
    data_df["Time"] = pd.to_datetime(data_df["Time"], format="%H:%M:%S")
    temp = data_df["Temperature"]
    humi = data_df["Humidity"]
    time = data_df["Time"]  

    # CLear previous plot
    ax.clear()
    
    # Set up the plot
    ax.set_ylim(0, 100)
    ax.set_xlabel("Time of the Day")
    ax.set_title("Temperature & Humidity Over 24 Hours")
    ax.grid(True, alpha=0.3) 

    temp_line, = ax.plot(time, temp, label="Temperature (°C)", color="red", linewidth=2)
    humi_line, = ax.plot(time, humi, label="Humidity (%)", color="blue", linewidth=2)
    ax.legend()

    # Set x-axis limits from 30 minutes before midnight (−0.5h) to 30 minutes past the next midnight (+24.5h)    
    midnight = datetime.strptime("00:00:00", "%H:%M:%S")
    ax.set_xlim(midnight - timedelta(hours=0.5), midnight + timedelta(hours=24.5))  

    ax.xaxis.set_major_locator(HourLocator(byhour=range(0, 25, 3)))  # Ticks at 00, 03, 06, ..., 24
    ax.xaxis.set_major_formatter(DateFormatter('%H:%M'))  # Format as HH:MM

   # Enable snap-to-point hover annotations to show values
    cursor = mplcursors.cursor([temp_line, humi_line], hover=True)
    @cursor.connect("add")
    def on_add(sel):
        x, y = sel.target
        x_dt = num2date(x)  # Convert float to datetime
        label = sel.artist.get_label()
        sel.annotation.set_text(f"{label}\nTime:{x_dt.strftime('%H:%M:%S')}\nValue:{y:.2f}")
        sel.annotation.get_bbox_patch().set(alpha=0.8, facecolor="lightyellow")
    canvas.draw()
        
# for adjusting the plot to show temperature only, humidity only or both
def adjust_graph():
    global temp_line, humi_line, canvas, ax, mode

    if temp_line is not None:
        temp_min, temp_max = min(temp_line.get_ydata()), max(temp_line.get_ydata())
        humi_min, humi_max = min(humi_line.get_ydata()), max(humi_line.get_ydata())

        if mode == "temp":
            temp_line.set_visible(True)
            humi_line.set_visible(False)
            mode = "humi"
            switch_plot_btn.configure(text="Show Humidity")

            ax.set_title("Temperature Over 24 Hours")
            ax.set_ylim(temp_min-0.5, temp_max+0.5)
            canvas.draw()

        elif mode == "humi":
            temp_line.set_visible(False)
            humi_line.set_visible(True)
            mode = "both"
            switch_plot_btn.configure(text="Show Both")


            ax.set_title("Humidity Over 24 Hours")
            ax.set_ylim(humi_min-2, humi_max+2)
            canvas.draw()

        elif mode == "both":
            temp_line.set_visible(True)
            humi_line.set_visible(True)
            mode = "temp"
            switch_plot_btn.configure(text="Show Temperature")

            ax.set_title("Temperature & Humidity Over 24 Hours")
            ax.set_ylim(0,100)
            canvas.draw()

def setup_graphtab():
    global fig, ax, toolbar, canvas, button_frame, switch_plot_btn

    # Create a new frame inside main_view
    title_frame = CTkFrame(master=graph_frame, fg_color="transparent")
    title_frame.pack(anchor="n", fill="x",  padx=27, pady=(29, 0))
    CTkLabel(master=title_frame, text="Graph", font=("Arial Black", 25), text_color="#2A8C55").pack(anchor="nw", side="left")

    button_frame = CTkFrame(master=graph_frame, fg_color="transparent")
    button_frame2 = CTkFrame(master=graph_frame, fg_color="transparent")
    
    # Figure initialization
    fig, ax = plt.subplots()
    plt.subplots_adjust(
        left=0.11,   # space from left of figure (0.0–1.0)
        right=None,  # space from right of figure (0.0–1.0)
        bottom=0.083, # space from bottom of figure (0.0–1.0)
        top=0.93,    # space from top of figure (0.0–1.0)
        wspace=None, # horizontal space between subplots
        hspace=None  # vertical space between subplots
    )
    
    canvas = FigureCanvasTkAgg(fig, master=graph_frame)
    switch_plot_btn = CTkButton(master=button_frame2, fg_color="#2A8C55", font=("Arial Bold", 14), text_color="#fff", hover_color="#216e43", text="Show Humidity", command=adjust_graph)
    toolbar = NavigationToolbar2Tk(canvas, graph_frame)
    show_date_dropdown(findall_csv())    
    
    button_frame.pack(anchor="n",  padx=27)
    canvas.get_tk_widget().pack(fill="both", expand=True, pady=0)   
    toolbar.pack_configure(anchor="center")
    switch_plot_btn.pack(anchor="n", fill="x",  padx=27)
    button_frame2.pack(anchor="n", padx=27, pady=(0,10))

def setup_settingtab():
    global thread_label, info_frame2

    title_frame = CTkFrame(master=setting_frame, fg_color="transparent")
    title_frame.pack(anchor="n", fill="x",  padx=27, pady=(29, 0))
    CTkLabel(master=title_frame, text="Setting", font=("Arial Black", 25), text_color="#2A8C55").pack(anchor="nw", side="left")

    info_frame1 = CTkFrame(master=setting_frame, fg_color="#2A8C55")
    info_frame1.pack(anchor="n", fill="x",  padx=27, pady=(36, 0))
    
    frequency_label = CTkLabel(master=info_frame1, text="Data frequency (in seconds):", text_color="white", font=("Arial Black", 15))
    frequency_label.grid(row=0, column=0, sticky="w", padx=(12, 5), pady=10)

    entry1 = CTkEntry(master=info_frame1, placeholder_text="e.g., 24", width=300, text_color="white", font=("Arial Black", 15), fg_color="transparent") 
    entry1.grid(row=0, column=1, sticky="w", padx=(12, 5), pady=10)

    no_data_label = CTkLabel(master=info_frame1, text="Number of data:", text_color="white", font=("Arial Black", 15))
    entry2 = CTkEntry(master=info_frame1, placeholder_text="e.g., 150", width=300, text_color="white", font=("Arial Black", 15), fg_color="transparent") 
    
    no_data_label.grid(row=1, column=0, sticky="w", padx=(12, 5), pady=10)
    entry2.grid(row=1, column=1, sticky="w", padx=(12, 5), pady=10)

    port_label = CTkLabel(master=info_frame1, text="SerialPort:", text_color="white", font=("Arial Black", 15))
    entry3 = CTkEntry(master=info_frame1, placeholder_text="e.g., COM6", width=300, text_color="white", font=("Arial Black", 15), fg_color="transparent") 
    
    port_label.grid(row=2, column=0, sticky="w", padx=(12, 5), pady=10)
    entry3.grid(row=2, column=1, sticky="w", padx=(12, 5), pady=10)

    # Insert default values into entry fields
    entry1.insert(0,"24")
    entry2.insert(0,"150")
    entry3.insert(0,"COM6")
    
    info_frame2 = CTkFrame(master=setting_frame, fg_color="#2A8C55")
    info_frame2.pack(anchor="n",  padx=27, pady=(70, 0))
    thread_label = CTkLabel(master=info_frame2, text="Receiver Status: Started", text_color="white", font=("Arial Black", 15))
    thread_label.pack(anchor="center", fill="x",  padx=27, pady=(20,20))

    button_frame = CTkFrame(master=setting_frame, fg_color="transparent")
    button_frame.pack(anchor="n",  padx=27, pady=(70, 0))

    startThread_button = CTkButton(master=button_frame, text="Start", command=lambda:startThread(entry1.get(),entry2.get(),entry3.get()), fg_color="#2A8C55", font=("Arial Bold", 16), text_color="white", hover_color="#216e43")
    startThread_button.pack(anchor="n",  padx=27, pady=(0, 0), ipady=2)

def setup_datatab():
    global data_folder, df, available_dates, file_time

    # Sort data and display filtered data
    def sort_value(selected):
        global df, treeview_initialize
        if selected == "Date ↑":
            df = df.sort_values(by=["Date", "Time"], ascending=[True, True])
        elif selected == "Date ↓":
            df = df.sort_values(by=["Date", "Time"], ascending=[False, False])
        elif selected == "Temperature ↑":
            df = df.sort_values(by="Temperature", ascending=True)
        elif selected == "Temperature ↓":
            df = df.sort_values(by="Temperature", ascending=False)
        elif selected == "Humidity ↑":
            df = df.sort_values(by="Humidity", ascending=True)
        elif selected == "Humidity ↓":
            df = df.sort_values(by="Humidity", ascending=False)
        
        data_list = df[df['Date'].isin(selected_dates)]
        data_list = data_list.values.tolist()

        tree.delete(*tree.get_children())

        # Setup treeview header if not initialized
        if treeview_initialize == False:
            style = ttk.Style()

            # Change body font
            style.configure("Custom.Treeview", font=("Arial", 12), rowheight=26)

            # Change heading font
            style.configure("Custom.Treeview.Heading", font=("Arial", 14, "bold"))

            headers = ["Date", "Time", "Temperature (°C)", "Humidity (%)"]
            tree["columns"] = headers
            for col in headers:
                tree.heading(col, text=col)
                tree.column(col, width=60, anchor="center")
            treeview_initialize = True

        # Insert all data
        for row in data_list[0:]:
            tree.insert("", "end", values=row)
        # Move scrollbar to the top
        tree.yview_moveto(0) 

    def filter_window(options):
        global available_dates
        # Disable refresh button to prevent bug
        refresh_btn.configure(state="disabled")
        filter_btn.configure(state="disabled")

        if available_dates is None:
            available_dates = {opt: BooleanVar(value=True) for opt in options}

        top = CTkToplevel(app)
        top.title("Select Dates")
        top.attributes("-topmost", True)
        top.geometry("250x400")

        # Scrollable frame inside the toplevel
        scroll_frame = CTkScrollableFrame(top, width=180, height=140)  
        scroll_frame.pack(padx=10, pady=10, fill="both", expand=True)

        def done():
            global selected_dates
            # Retrieve the actual True/False values 
            selected_dates = [opt for opt, var in available_dates.items() if var.get()]
            top.destroy()
            refresh_btn.configure(state="enable")
            filter_btn.configure(state="enable")
            sort_value(sort_box.get()) # show the updated filtered data

        # Select all available dates
        def select_all():
            for var in available_dates.values():
                var.set(True)

        # Deselect all available dates
        def remove_all():
            for var in available_dates.values():
                var.set(False)
        
        # Close the pop-up window but did not filter the data
        def on_close():
            # Re-enable the refresh button always
            refresh_btn.configure(state="enable")
            filter_btn.configure(state="enable")
            top.destroy()

        # Add checkboxes for each option
        for opt in options:
            CTkCheckBox(
                scroll_frame,
                text=opt,
                variable=available_dates[opt]
            ).pack(anchor="center", padx=10, pady=2)

        # Buttons row
        btn_frame = CTkFrame(top, fg_color="transparent")
        btn_frame.pack(pady=5)
        
        CTkButton(btn_frame, text="Select All", command=select_all, width=60).pack(side="left", padx=5)
        CTkButton(btn_frame, text="Remove All", command=remove_all, width=60).pack(side="left", padx=5)

        # Done button closes the dropdown and runs callback
        CTkButton(top, text="Done", command=done, width=60).pack(pady=10)
        # Handle window close (clicking the ❌)
        top.protocol("WM_DELETE_WINDOW", on_close)

    def refresh():
        global df, selected_dates, available_dates, file_time
        # Refresh all variables
        file_list = []
        df = [] 
        file_time = findall_csv()
        selected_dates = findall_csv()
        available_dates = None
        
        # Execute only if file_time is not empty (which means at least one CSV file exists)
        if file_time:
            for i in range(len(file_time)):
                file_list.append(f"data_log/data_{file_time[i]}.csv")
                temp_df = pd.read_csv(file_list[i])
                # add date to the data
                temp_df.insert(0, "Date","1900-01-01")
                temp_df["Date"] = file_time[i]
                df.append(temp_df)
            df = pd.concat(df)
            sort_value("Date ↑")
            sort_box.set("Date ↑")       
            print(f"{datetime.now().strftime("%Y-%m-%d %H:%M:%S")} --> Data tab refreshed.")

    title_frame = CTkFrame(master=data_frame, fg_color="transparent")
    title_frame.pack(anchor="n", fill="x",  padx=27, pady=(29, 0))
    sort_container = CTkFrame(master=data_frame, height=50, fg_color="#F0F0F0")
    sort_container.pack(fill="x", pady=(45, 0), padx=27)
    sort_options = ["Date ↑", "Date ↓", "Temperature ↑", "Temperature ↓", "Humidity ↑", "Humidity ↓"]
    sort_box = CTkComboBox(master=sort_container, command=sort_value, width=125, values= sort_options, button_color="#2A8C55", border_color="#2A8C55", border_width=2, button_hover_color="#207244",dropdown_hover_color="#207244" , dropdown_fg_color="#2A8C55", dropdown_text_color="#fff")
    filter_btn = CTkButton(master=sort_container, command=lambda:filter_window(file_time), fg_color="#2A8C55", font=("Arial Bold", 14), text_color="#fff", hover_color="#216e43", text="Filter")
    refresh_btn = CTkButton(master=sort_container, command=lambda:refresh(), fg_color="#2A8C55", font=("Arial Bold", 14), text_color="#fff", hover_color="#216e43", text="Refresh")
    
    sort_box.pack(side="right", padx=(13,13), pady=15)
    filter_btn.pack(side="right", padx=(13,13), pady=15)
    refresh_btn.pack(side="right", padx=(13,13), pady=15)
  
    container_frame = CTkFrame(master=data_frame, fg_color="transparent")
    container_frame.pack(anchor="n", fill="both", expand=True, padx=27, pady=(29, 0))
    CTkLabel(master=title_frame, text="Data", font=("Arial Black", 25), text_color="#2A8C55").pack(anchor="nw", side="left")
    
    # Container for both Treeview and Scrollbar
    table_frame = CTkFrame(master=container_frame, fg_color="transparent")
    table_frame.pack(fill="both", expand=True)
    tree = ttk.Treeview(table_frame, show="headings", style="Custom.Treeview")
    vsb = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=vsb.set)
    # Layout: Treeview on the left, Scrollbar on the right
    tree.pack(side="left", fill="both", expand=True, pady=(0,40))
    vsb.pack(side="right", fill="y", pady=(0,40), padx=(10,0))
    refresh()

def start_timer():
    """Start a countdown timer (default: 3600s)"""
    global end_time, running, timer_duration
    end_time = time.time() + timer_duration
    running = True
    # print("Timer started")

def get_time_left():
    """Return how many seconds are left"""
    if not running or end_time is None:
        return timer_duration
    remaining = end_time - time.time()
    return max(0, int(remaining))

def reset_timer():
    """Reset timer back to original duration"""
    global end_time, running
    if running:  # only reset if timer is running
        end_time = time.time() + timer_duration
        # print("Timer reset")

def stop_timer():
    """Stop the countdown"""
    global running, end_time
    running = False
    end_time = None
    # print("Timer stopped")

def check_timer():
    """This function is to check whether timer has run out of time every 5s using customtkinter gui loop"""
    if Serial_read.reset_timer_flag == True:
        reset_timer()
        Serial_read.reset_timer_flag = False
        
    if running:
        left = get_time_left()
        if left <= 0:
            # print("\nTimer finished.")
            notif_telegram("⚠️Check the sensor node (Arduino Pro Mini). Haven't received data for 1 hour.")
            reset_timer()

    app.after(5000, check_timer)  # check every 5s

def checkThread_status():
    global t, info_frame2
    if t.is_alive():
        app.after(500, checkThread_status)
    else:
        thread_label.configure(text=f"Receiver Status: Not started", text_color="#594747")
        # Stop the timer if it is running
        if running:
            stop_timer()
        app.after(500, checkThread_status)

def startThread(frequency,no_dataset,port):
    global thread_label, t, info_frame2
    # if thread already existed then return, else start new thread
    if t.is_alive():
        print(f"{datetime.now().strftime("%Y-%m-%d %H:%M:%S")} --> Thread start failed. Reason: Thread has already started")
        return
    
    # Open the config file
    config = configparser.ConfigParser()
    config.read("config.ini")

    # Update the config file
    config["Serial"]["data_frequency"] = frequency
    config["Serial"]["numbers_of_datasets"] = no_dataset
    config["Serial"]["port"] = port
    with open("config.ini", "w") as configfile:
        config.write(configfile)

    t = threading.Thread(target=serial_read, daemon=True)
    t.start()
    start_timer()
    check_timer()
    thread_label.configure(text=f"Receiver Status: Started", text_color="white")

# Main code
if __name__ == '__main__':
    try:
        # all function in main is to initialize the gui and display the gui
        app = CTk()
        app.geometry("856x645")
        app.title("Sensor Node Dashboard")
        app.resizable(0,0)

        set_appearance_mode("light")
        sidebar_frame = CTkFrame(master=app, fg_color="#2A8C55",  width=176, height=650, corner_radius=0)
        sidebar_frame.pack_propagate(0)
        
        sidebar_frame.pack(fill="y", anchor="w", side="left")

        setting_img_data = Image.open("image/setting.jpg")
        setting_img = CTkImage(dark_image=setting_img_data, light_image=setting_img_data)

        graph_img_data = Image.open("image/graph.jpg")
        graph_img = CTkImage(dark_image=graph_img_data, light_image=graph_img_data)

        data_img_data = Image.open("image/temp_icon.jpg")
        data_img = CTkImage(dark_image=data_img_data, light_image=data_img_data)

        tab_containter = CTkFrame(master=app, fg_color="white",  width=680, height=650, corner_radius=0)
        tab_containter.pack_propagate(0)
        tab_containter.pack(side="left")

        def switch_tab(Tab):
            if (Tab == "setting"):
                setting_frame.pack(fill="both",expand=True)
                graph_frame.pack_forget()
                data_frame.pack_forget()

                setting_btn.configure(fg_color=sel_fgcolor, text_color=sel_txtcolor, hover_color=sel_hovercolor)
                graph_btn.configure(fg_color=unsel_fgcolor, text_color=unsel_txtcolor, hover_color=unsel_hovercolor)
                data_btn.configure(fg_color=unsel_fgcolor, text_color=unsel_txtcolor, hover_color=unsel_hovercolor)

            if (Tab == "graph"):
                graph_frame.pack(fill="both",expand=True)
                setting_frame.pack_forget()
                data_frame.pack_forget()

                graph_btn.configure(fg_color=sel_fgcolor, text_color=sel_txtcolor, hover_color=sel_hovercolor)
                setting_btn.configure(fg_color=unsel_fgcolor, text_color=unsel_txtcolor, hover_color=unsel_hovercolor)
                data_btn.configure(fg_color=unsel_fgcolor, text_color=unsel_txtcolor, hover_color=unsel_hovercolor)

                # update the date combobox
                show_date_dropdown(findall_csv())

            if (Tab == "data"):
                data_frame.pack(fill="both",expand=True)
                setting_frame.pack_forget()
                graph_frame.pack_forget()

                data_btn.configure(fg_color=sel_fgcolor, text_color=sel_txtcolor, hover_color=sel_hovercolor)
                setting_btn.configure(fg_color=unsel_fgcolor, text_color=unsel_txtcolor, hover_color=unsel_hovercolor)
                graph_btn.configure(fg_color=unsel_fgcolor, text_color=unsel_txtcolor, hover_color=unsel_hovercolor)

        
        # Create tabs using frames
        setting_frame = CTkFrame(master=tab_containter, fg_color="white")
        graph_frame = CTkFrame(master=tab_containter, fg_color="white")
        data_frame = CTkFrame(master=tab_containter, fg_color="white")

        # Setup sidebar buttons
        setting_btn = CTkButton(master=sidebar_frame, command=lambda:switch_tab("setting"), image=setting_img, text="Setting", fg_color=unsel_fgcolor, 
                                font=("Arial Bold", 14), text_color=unsel_txtcolor, hover_color=unsel_hovercolor, anchor="w")
        graph_btn = CTkButton(master=sidebar_frame, command=lambda:switch_tab("graph"), image=graph_img, text="Graph", fg_color=sel_fgcolor, 
                            font=("Arial Bold", 14), text_color=sel_txtcolor, hover_color=sel_hovercolor, anchor="w")
        data_btn = CTkButton(master=sidebar_frame, command=lambda:switch_tab("data"), image=data_img, text="Data", fg_color=unsel_fgcolor, 
                                font=("Arial Bold", 14), text_color=unsel_txtcolor, hover_color=unsel_hovercolor, anchor="w")
        setting_btn.pack(anchor="center", ipady=5, pady=(60, 0))
        graph_btn.pack(anchor="center", ipady=5, pady=(16, 0))
        data_btn.pack(anchor="center", ipady=5, pady=(16, 0))
        
        setup_settingtab()
        setup_graphtab()
        setup_datatab()
        switch_tab("setting")
        checkThread_status()
        adjust_graph()

        print("All available ports:")
        ports = list_ports.comports()
        for port in ports: print(f"\t{port}")

        # Start telegram bot as multiprocess
        multiprocessing.set_start_method("spawn")  
        bot_process.start()
        notif_telegram("--------------------------------------------\n 🤖 🟢 Bot is now online!")

        def on_closing():
            print("Program is terminated.")
            notif_telegram("🤖 🔴 Bot is now offline.")
            bot_process.terminate()
            os._exit(0)

        app.protocol("WM_DELETE_WINDOW", on_closing)
        app.mainloop()  

    except KeyboardInterrupt: 
        on_closing()