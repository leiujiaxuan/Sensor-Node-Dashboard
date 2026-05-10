#include <LowPower.h>
#include <DHT.h>
#include <SoftwareSerial.h>
#include <avr/power.h>

//Constants
#define DHTPIN 2           // DHT22 connected to pin 2
#define DHTTYPE DHT22      // DHT 22  (AM2302)
#define HC12SETPIN 10       // Pin 10 used to send command to HC-12 Transceiver
#define MAXLOOP 150       // Number of datasets per transmission
#define HC12 Serial
// #define DEBUG Serial
// #define DEBUG_SERIAL  

// #define DEBUG_RF
// #define DEBUG_TIME
// SoftwareSerial DEBUG(10, 11);  // RX=10, TX=11

// === Variables === //
int counter = 0;
extern volatile unsigned long timer0_millis;
float temp_threshold = 31.0;

#ifdef DEBUG_TIME
  unsigned long startTime;
  unsigned long elapsedTime;
#endif

struct dht_data_structure {
  float temp;
  float humi;
};

struct dht_data_structure dht_data[MAXLOOP];
DHT dht(DHTPIN, DHTTYPE);  
// ------------------------------------------------------------------- //

void setup() {
  //  ==== Added power saving feature =======
  ADCSRA = 0;     // disable ADC
  power_all_disable();
  power_timer0_enable();
  power_usart0_enable();
  // ------------------------ //
  
  HC12.begin(38400); // Initailize Serial Port connected to the HC-12 to 38400 Baud Rate
  pinMode(DHTPIN, INPUT); 
  dht.begin();

  // Pull down Pin 8 to enable the RF Transceiver to receive command
  pinMode(HC12SETPIN, OUTPUT);
  digitalWrite(HC12SETPIN, LOW);
  delay(40);

  // Initialize HC-12 Transceiver
  HC12.print("AT+FU3");   // Set HC-12 working mode
  delay(40);
  HC12.print("AT+B38400"); // Set HC-12 Baud Rate
  delay(40);
  HC12.print("AT+P4");    // Set HC-12 Transmitting Power
  delay(40);
  #ifdef DEBUG_RF
    char rc;
    while (HC12.available() > 0) {
      rc = HC12.read();
      HC12.print(rc);
    }
  #endif
  digitalWrite(HC12SETPIN, HIGH);   // Exits command mode, enabling RF transmission
  delay(80);

  // Send text to test connectivity to the receiver
  HC12.println("This is test code from sensor node.");
  delay(2000);
  digitalWrite(HC12SETPIN, LOW);
  delay(40);
  HC12.print("AT+SLEEP");
  delay(40);
  digitalWrite(HC12SETPIN, HIGH);   // Exits command mode, enabling RF transmission
  delay(80);
}

void loop() {
  // 1st and 2nd of readings are only for fire detection.
  // Only the 3rd reading will actually be stored to the memory and used for plot graph etc.

  // =========== 1st read ============ //
  #ifdef DEBUG_TIME
    startTime = micros();
  #endif
  get_dhtdata(dht_data[counter].temp, dht_data[counter].humi);
  check_fire();
  
  #ifdef DEBUG_TIME
    elapsedTime = micros() - startTime;
    DEBUG.print("Elapsed Time: ");
    DEBUG.println(elapsedTime);
    DEBUG.flush();
  #endif
  LowPower.powerDown(SLEEP_8S, ADC_ON, BOD_OFF); // ADC_ON to let the ADC power state untouched (off)


  // =========== 2nd read ============ //
  #ifdef DEBUG_TIME
    startTime = micros();
  #endif
  get_dhtdata(dht_data[counter].temp, dht_data[counter].humi);
  check_fire();

  #ifdef DEBUG_TIME
    elapsedTime = micros() - startTime;
    DEBUG.print("Elapsed Time: ");
    DEBUG.println(elapsedTime);
    DEBUG.flush();
  #endif
  LowPower.powerDown(SLEEP_8S, ADC_ON, BOD_OFF); // ADC_ON to let the ADC power state untouched (off)

  // =========== 3rd read ============ //
  #ifdef DEBUG_TIME
    startTime = micros();
  #endif
  get_dhtdata(dht_data[counter].temp, dht_data[counter].humi);
  check_fire();
  counter++;
  if (counter == MAXLOOP) {
    send_data();
    counter=0;
  }
  #ifdef DEBUG_TIME
    elapsedTime = micros() - startTime;
    DEBUG.print("Elapsed Time: ");
    DEBUG.println(elapsedTime);
    DEBUG.flush();
  #endif
  LowPower.powerDown(SLEEP_8S, ADC_ON, BOD_OFF); // ADC_ON to let the ADC power state untouched (off)
}


// ================= Functions ================= //

// get humi and temp from DHT22 sensor
void get_dhtdata(float& temp, float& humi) {
  timer0_millis += 20;
  humi = dht.readHumidity();
  temp = dht.readTemperature();

  #ifdef DEBUG_SERIAL
  // Display obtained temp and humi value to terminal for debug
    DEBUG.print("Temperature: ");
    DEBUG.print(temp);
    DEBUG.print("ºC  ");
    DEBUG.print("Humidity: ");
    DEBUG.print(humi);
    DEBUG.println("%");
    DEBUG.flush();
  #endif
}

// Send Data to RF Transceiver
void send_data() {
  // Wake up RF Transceiver
  digitalWrite(HC12SETPIN, LOW);
  delay(50);
  digitalWrite(HC12SETPIN, HIGH);
  delay(80);

  // Send humi and temp to RF Transceiver in the format of: <temp,humi>
  for(int i=0; i<MAXLOOP; i++){
    HC12.print("<");
    HC12.print(dht_data[i].temp);
    HC12.print(",");
    HC12.print(dht_data[i].humi);
    HC12.print(">");
  }

  HC12.print("\n") ;
  HC12.flush(); // Wait for the data to finish transmitting to HC-12
  delay(200);  // **** this delay is needed to make sure HC-12 has already sent all the data
  

  // Change RF Transceiver back to sleep mode
  digitalWrite(HC12SETPIN, LOW);
  delay(50);
  HC12.print("AT+SLEEP");
  delay(50);
  HC12.flush();

  #ifdef DEBUG_RF
    // receive confirm message from RF Transceiver
    while (HC12.available()) {
      char mg2;
      mg2 = HC12.read();
      DEBUG.print(mg2);  //print out confirm mode change message from RF Transceiver
    }
  #endif

  digitalWrite(HC12SETPIN, HIGH);   // Exits command mode, enabling RF transmission
}

void check_fire(){
  // If current temperature > threshold then send warning and current readings immediately
  // Example Output:  Fire Detected
  //                  24.7,66.7
  if (dht_data[counter].temp > temp_threshold) {
    // Wake up RF Transceiver
    digitalWrite(HC12SETPIN, LOW);
    delay(40);
    digitalWrite(HC12SETPIN, HIGH);
    delay(80);    

    // Send warning
    HC12.println("Fire Detected");
    HC12.print(dht_data[counter].temp);
    HC12.print(",");
    HC12.println(dht_data[counter].humi);
    HC12.flush();
    delay(200);

    // Change RF Transceiver back to power saving mode (FU2)
    digitalWrite(HC12SETPIN, LOW);
    delay(50);
    HC12.print("AT+SLEEP");
    delay(50);
    digitalWrite(HC12SETPIN, HIGH);
  }
}


