#include <Arduino.h>
#include "esp_camera.h"
#include <WiFi.h>
#include <PubSubClient.h>

// ===========================
// Select camera model in board_config.h
// ===========================
#include "board_config.h"

// ===========================
// WiFi credentials (secrets.h, fora do git)
// ===========================
#include "secrets.h"
const char *ssid = WIFI_SSID;
const char *password = WIFI_PASSWORD;

// ===========================
// MQTT
// ===========================
const char *mqttClientId = "esp32cam-cam1";
const char *topicoPedido = "ovitrampa/cam1/capturar";
const char *topicoFoto = "ovitrampa/cam1/foto";

WiFiClient wifiClient;
PubSubClient mqtt(wifiClient);
volatile bool pedidoFoto = false;
unsigned long ultimaTentativaMqtt = 0;

void startCameraServer();
void setupLedFlash();

void mqttCallback(char *topic, byte *payload, unsigned int length) {
  pedidoFoto = true;
}

void setup() {
  Serial.begin(115200);
  Serial.setDebugOutput(true);
  Serial.println();

  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk = XCLK_GPIO_NUM;
  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href = HREF_GPIO_NUM;
  config.pin_sccb_sda = SIOD_GPIO_NUM;
  config.pin_sccb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.frame_size = FRAMESIZE_UXGA;
  config.pixel_format = PIXFORMAT_JPEG;
  config.grab_mode = CAMERA_GRAB_WHEN_EMPTY;
  config.fb_location = CAMERA_FB_IN_PSRAM;
  config.jpeg_quality = 12;
  config.fb_count = 2;

  if (config.pixel_format == PIXFORMAT_JPEG) {
    if (psramFound()) {
      config.jpeg_quality = 10;
      config.fb_count = 2;
      config.grab_mode = CAMERA_GRAB_LATEST;
    } else {
      config.frame_size = FRAMESIZE_SVGA;
      config.fb_location = CAMERA_FB_IN_DRAM;
    }
  } else {
    config.frame_size = FRAMESIZE_240X240;
#if CONFIG_IDF_TARGET_ESP32S3
    config.fb_count = 2;
#endif
  }

#if defined(CAMERA_MODEL_ESP_EYE)
  pinMode(13, INPUT_PULLUP);
  pinMode(14, INPUT_PULLUP);
#endif

  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("Camera init failed with error 0x%x", err);
    return;
  }

  sensor_t *s = esp_camera_sensor_get();
  Serial.printf("Sensor detectado - PID: 0x%x\n", s->id.PID);

  if (s->id.PID == OV3660_PID) {
    s->set_vflip(s, 1);
    s->set_brightness(s, 1);
    s->set_saturation(s, -2);
  }

  if (config.pixel_format == PIXFORMAT_JPEG) {
    s->set_framesize(s, FRAMESIZE_SVGA);
  }

#if defined(LED_GPIO_NUM)
  setupLedFlash();
#endif

  WiFi.begin(ssid, password);
  WiFi.setSleep(false);

  Serial.print("WiFi connecting");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("");
  Serial.println("WiFi connected");

  startCameraServer();

  Serial.print("Camera Ready! Use 'http://");
  Serial.print(WiFi.localIP());
  Serial.println("' to connect");

  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  mqtt.setCallback(mqttCallback);
}

void loop() {
  if (!mqtt.connected()) {
    if (millis() - ultimaTentativaMqtt >= 5000) {
      ultimaTentativaMqtt = millis();
      if (mqtt.connect(mqttClientId)) {
        Serial.println("MQTT conectado");
        mqtt.subscribe(topicoPedido);
      } else {
        Serial.printf("MQTT falhou, state=%d\n", mqtt.state());
      }
    }
  }
  mqtt.loop();

  if (pedidoFoto) {
    pedidoFoto = false;
    Serial.println("Pedido recebido");

    camera_fb_t *fb = esp_camera_fb_get();
    if (!fb) {
      Serial.println("Falha ao capturar foto");
      return;
    }

    bool ok = mqtt.beginPublish(topicoFoto, fb->len, false);
    if (ok) {
      ok = mqtt.write(fb->buf, fb->len) == fb->len;
      ok = mqtt.endPublish() && ok;
    }
    if (ok) {
      Serial.printf("Foto enviada: %u bytes\n", fb->len);
    } else {
      Serial.printf("Falha ao enviar foto (%u bytes), state=%d\n", fb->len, mqtt.state());
    }
    esp_camera_fb_return(fb);
  }
}