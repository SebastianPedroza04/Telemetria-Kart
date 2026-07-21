let line = msg.payload.toString().trim();

if (!line) return null;

if (
    line.startsWith("===") ||
    line.startsWith("LoRa") ||
    line.startsWith("seq") ||
    line.startsWith("ERROR") ||
    line.startsWith("ets") ||
    line.startsWith("rst:")
) {
    return null;
}

let p = line.split(",");

// seq,t_us,ax,ay,az,gx,gy,gz,roll,pitch,g_lat,g_lon,yaw_rate,rssi,snr,lost,total
if (p.length < 17) {
    return null;
}

let data = {
    seq: Number(p[0]),
    t_us: Number(p[1]),
    ax: Number(p[2]),
    ay: Number(p[3]),
    az: Number(p[4]),
    gx: Number(p[5]),
    gy: Number(p[6]),
    gz: Number(p[7]),
    roll: Number(p[8]),
    pitch: Number(p[9]),
    g_lat: Number(p[10]),
    g_lon: Number(p[11]),
    yaw_rate: Number(p[12]),
    rssi: Number(p[13]),
    snr: Number(p[14]),
    lost: Number(p[15]),
    total: Number(p[16])
};

if (
    Number.isNaN(data.seq) ||
    Number.isNaN(data.roll) ||
    Number.isNaN(data.pitch)
) {
    return null;
}

msg.payload = data;
return msg;
