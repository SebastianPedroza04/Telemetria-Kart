// Usar una función por variable, conectada después de parse_telemetria.

// Roll
msg.payload = Number(msg.payload.roll);
msg.topic = "Roll";
return msg;

// Pitch
msg.payload = Number(msg.payload.pitch);
msg.topic = "Pitch";
return msg;

// G lateral
msg.payload = Number(msg.payload.g_lat);
msg.topic = "G lateral";
return msg;

// G longitudinal
msg.payload = Number(msg.payload.g_lon);
msg.topic = "G longitudinal";
return msg;

// Yaw rate
msg.payload = Number(msg.payload.yaw_rate);
msg.topic = "Yaw rate";
return msg;

// RSSI
msg.payload = Number(msg.payload.rssi);
msg.topic = "RSSI LoRa";
return msg;

// SNR
msg.payload = Number(msg.payload.snr);
msg.topic = "SNR";
return msg;

// Paquetes perdidos
msg.payload = Number(msg.payload.lost);
msg.topic = "Paquetes perdidos";
return msg;
