// Slave-to-master state machine
// Source: Appendix III of the thesis "Diseño de una puerta de enlace entre una red Modbus RTU y un servidor MQTT
// para transmisión y recepción de datos" (María Ángel Milano, UCV, 2022). ESP32 + FreeRTOS (ESP-IDF via PlatformIO),
// Arduino libraries WiFi, PubSubClient and ArduinoJson. Transcribed from the thesis PDF; helper functions
// (int_to_json, json_to_int, wifi_connect, reconnect), queues and globals live in other modules not printed in the thesis.

static void maq_estados_slave_to_master(void *pvParameters){
enum estados_slave_to_master estados = SUSCRIPCION_;
struct buffer_data rx_buffer;
struct buffer_data tx_buffer;
uint8_t cont = 0;
uint8_t state_loop = 0;
uint8_t return_subscribe = 0;
esp_task_wdt_add(NULL);
 for(;;) {
  switch(estados){
   case SUSCRIPCION_:
    uart_write_bytes(UART_NUM_0, "suscripcion\n\r",13);
    wifi_connect();
    state_loop = client.loop();
    return_subscribe = client.subscribe(TOPIC_MASTER_TO_SLAVE,0);
    if(return_subscribe && state_loop){
     gpio_set_level((gpio_num_t)LED_VERDE,1);
     estados = ESPERA_TOPIC_;}
    else
     blink_activate = BLINK_VERDE;
     vTaskDelay(2000/portTICK_RATE_MS);
break;
case ESPERA_TOPIC_:
return_subscribe = client.subscribe(TOPIC_MASTER_TO_SLAVE,0);
state_loop = client.loop();
sincronismo_mqtt = 1;
bzero(rx_buffer.dato,BUFFER_SIZE);
if(state_loop && return_subscribe){
 if (xQueueReceive(queue_mqtt,&rx_buffer,5000/portTICK_RATE_MS)){
  estados = DESENCAPSULAR_JSON_;
  esp_task_wdt_reset();
  }
 }
 else{
  blink_activate = BLINK_ROJO;
  estados = SUSCRIPCION_;}
  sincronismo_mqtt = 0;
 break;
case DESENCAPSULAR_JSON_:
uart_write_bytes(UART_NUM_0, "des_json\n\r",10);
bzero(tx_buffer.dato,BUFFER_SIZE);
tx_buffer = json_to_int(rx_buffer, &cont);
estados = TRANSMITIR_RS485_;
break;
case TRANSMITIR_RS485_:
uart_write_bytes(UART_NUM_0, "tx_485\n\r",8);
uart_write_bytes(UART_NUM_1, (const char*)tx_buffer.dato,
      tx_buffer.size);
estados = ESPERA_RS485_;
break;
case ESPERA_RS485_:
uart_write_bytes(UART_NUM_0, "rx_485\n\r",8);
bzero(rx_buffer.dato,BUFFER_SIZE);
if (xQueueReceive(queue_rx1,&rx_buffer,10000/portTICK_RATE_MS)) {
  estados = ENCAPSULAR_JSON_;
  }
else {
  blink_activate = BLINK_ROJO;
  estados = ESPERA_TOPIC_;}
break;
case ENCAPSULAR_JSON_:
uart_write_bytes(UART_NUM_0, "enc_json\n\r",10);
bzero(tx_buffer.dato,BUFFER_SIZE);
tx_buffer = int_to_json(rx_buffer, cont);
estados = PUBLICAR_;
break;
case PUBLICAR_:
uart_write_bytes(UART_NUM_0, "pub\n\r",5);
if (!client.connected()) {
 reconnect();
 blink_activate = BLINK_VERDE;
 }
client.publish(TOPIC_SLAVE_TO_MASTER, (char *)tx_buffer.dato);
blink_activate = BLINK_AZUL;
estados = ESPERA_TOPIC_;
    break;
    default:
    estados = ESPERA_TOPIC_;
    break;
                 }
             }
     vTaskDelete(NULL);
}
