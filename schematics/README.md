# Esquemáticos

Esta pasta vai receber o esquemático do hardware:

- ESP32-CAM AI Thinker + programador ESP32-CAM-MB + fonte 5 V;
- arquivos: Fritzing (`.fzz`) e imagem (`.png`).

## Ligações da câmera (já feitas na placa)

A câmera OV2640 vem ligada à ESP32 na própria AI Thinker. Os pinos estão em `esp32-esp8266/include/camera_pins.h`, bloco `CAMERA_MODEL_AI_THINKER`.

| Sinal | GPIO |
|---|---|
| PWDN | 32 |
| XCLK | 0 |
| SIOD (SDA) | 26 |
| SIOC (SCL) | 27 |
| D7 | 35 |
| D6 | 34 |
| D5 | 39 |
| D4 | 36 |
| D3 | 21 |
| D2 | 19 |
| D1 | 18 |
| D0 | 5 |
| VSYNC | 25 |
| HREF | 23 |
| PCLK | 22 |
