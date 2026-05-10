# What This Program Does
This project is a desktop dashboard for an Arduino-based sensor node (built for my Final Year Project).

- Reads temperature/humidity data from the receiver via Serial (COM port).
- Saves readings into daily CSV files in `data_log/`.
- Shows the data in the GUI (table + interactive 24-hour plots).
- Sends alerts when a “Fire Detected” event is received (desktop notification + Telegram message + email).
- Runs a Telegram bot so you can request the CSV logs and generated plot images remotely.
- Settings (COM port, frequency, alert destinations) are configured in `config.ini`.

# How to Run The Dashboard
Download Python 3.13.0 and Visual Studio Code (VSCode)

Open VSCode and install Python Extension
- Press Ctrl+Shift+X to open the Extensions panel.
- Search for Python and install the one by Microsoft.

Required Libraries:

    • customtkinter  
    • pillow  
    • pyserial  
    • matplotlib  
    • mplcursors  
    • pandas  
    • python-telegram-bot  
    • plyer  
    • yagmail  
    • win11toast 

Can be installed using this command:

    pip install customtkinter pillow pyserial matplotlib mplcursors pandas python-telegram-bot plyer yagmail win11toast 

** Do note that customtkinter does not work well with virtual envinronment I think.

Email alert settings

- To change where fire-alert emails are sent, edit `email_receiver` in `config.ini`.
- If you use Gmail, you must generate a Gmail **App Password** and put it into `app_password` in `config.ini`:

    https://support.google.com/mail/thread/205453566/how-to-generate-an-app-password?hl=en

Run the program

- Run `main.py`.

About “Data frequency (seconds)” in the GUI

- This value should match the **time between each sensor reading** produced by `SensorNode.ino`.
- In the provided Arduino code, that interval is the sum of the delays between readings:

    loop interval ≈ (1st read sleep) + (2nd read sleep) + (3rd read sleep)

- Example: if each sleep is 8 seconds, then the interval is `8 + 8 + 8 = 24` seconds.
