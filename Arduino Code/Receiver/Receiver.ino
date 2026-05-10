#define HC12SETPIN 7  // Pin A1 used to send command to HC-12 Transceiver
#define HC12 Serial
char rc;

void setup()
{
  HC12.begin(38400); // port connected to HC-12 Transceiver
  pinMode(HC12SETPIN, OUTPUT);
  digitalWrite(HC12SETPIN, LOW);
  delay(80);

  // Change RF Transceiver to FU3 mode
  HC12.print("AT+FU3");
  delay(80);
  HC12.print("AT+B38400");
  delay(150);

  digitalWrite(HC12SETPIN, HIGH);   // Exits command mode, enabling RF transmission
  delay(1000);
}

void loop()
{
  while (HC12.available() > 0) {
      rc = HC12.read();
      Serial.print(rc);
  }
}
