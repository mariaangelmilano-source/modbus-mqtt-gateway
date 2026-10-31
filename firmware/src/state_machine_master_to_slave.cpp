// Master-to-slave state machine
// Source: Appendix II of the thesis "Diseño de una puerta de enlace entre una red Modbus RTU y un servidor MQTT
// para transmisión y recepción de datos" (María Ángel Milano, UCV, 2022). ESP32 + FreeRTOS (ESP-IDF via PlatformIO),
// Arduino libraries WiFi, PubSubClient and ArduinoJson. Transcribed from the thesis PDF; helper functions
// (int_to_json, json_to_int, wifi_connect, reconnect), queues and globals live in other modules not printed in the thesis.

static void maq_estados_master_to_slave(void *pvParameters){
enum estados_master_to_slave estados = ESPERA_RS485;
struct buffer_data rx_buffer;
struct buffer_data tx_buffer;
uint8_t contador_tx = 0;
uint8_t contador_rx = 0;
uint8_t state_loop = 0;
uint8_t return_subscribe = 0;
uint8_t intentos = 0;
esp_task_wdt_add(NULL);
 for(;;) {
   switch(estados){
     case ESPERA_RS485:
       bzero(rx_buffer.dato,BUFFER_SIZE);
       if (xQueueReceive(queue_rx1,&rx_buffer,3000/portTICK_RATE_MS)){
        esp_task_wdt_reset();
        contador_tx == 200 ? contador_tx=0 : contador_tx++;
        estados = ENCAPSULAR_JSON;          }
       else
        blink_activate = BLINK_ROJO;
     break;
     case ENCAPSULAR_JSON:
 bzero(tx_buffer.dato,BUFFER_SIZE);
 tx_buffer = int_to_json(rx_buffer, contador_tx);
 estados = SUSCRIPCION;
break;
case SUSCRIPCION:
 wifi_connect();
 gpio_set_level((gpio_num_t)LED_VERDE, 1);
 state_loop = client.loop();
 return_subscribe = client.subscribe(TOPIC_SLAVE_TO_MASTER,0);
 client.subscribe(TOPIC_SLAVE_TO_MASTER,0);
     if(state_loop && return_subscribe){
         gpio_set_level((gpio_num_t)LED_VERDE, 1);
         intentos=0;
         estados = PUBLICAR;
         }
     else{
         if(intentos == 5){
             blink_activate = BLINK_VERDE;
             estados = ESPERA_RS485;
             intentos = 0;
         }
         else
             intentos++;
             }
         break;
case PUBLICAR:
 if (!client.connected()) {
   blink_activate = BLINK_VERDE;
   reconnect();
   }
 client.loop();
 client.publish(TOPIC_MASTER_TO_SLAVE, (char *)tx_buffer.dato);
 estados = ESPERA_TOPIC;
break;
case ESPERA_TOPIC:
 sincronismo_mqtt = 1;
 bzero(rx_buffer.dato,BUFFER_SIZE);
 if (xQueueReceive(queue_mqtt,&rx_buffer,10000/portTICK_RATE_MS))
   estados = DESENCAPSULAR_JSON;
 else
   {
   estados = ESPERA_RS485;
   blink_activate = BLINK_ROJO;
   }
 sincronismo_mqtt = 0;
break;
case DESENCAPSULAR_JSON:
 bzero(tx_buffer.dato,BUFFER_SIZE);
 tx_buffer = json_to_int(rx_buffer, &contador_rx);
 if(contador_tx == contador_rx){
   estados = TRANSMITIR_RS485;
   blink_activate = BLINK_AZUL;
   }
 else {
   estados = ESPERA_RS485;}
break;
    case TRANSMITIR_RS485:
     for(uint8_t p=0; p<tx_buffer.size; p++)
       uart_write_bytes(UART_NUM_1, (const char*)tx_buffer.dato,
             tx_buffer.size);
       estados = ESPERA_RS485;
    break;
    default:
     estados = ESPERA_RS485;
    break;
                }
         }
    vTaskDelete(NULL);
}
