/**
 * ================================================================
 *  MiTV 24/7 YouTube Live Stream Workflow
 *  Author : Muaaz Iqbal | MiTV Network / MuslimIslam Organization
 *  Config : config.yml | playlist.json | bar.json
 * ================================================================
 */

const { spawn, execSync } = require("child_process");
const fs    = require("fs");
const path  = require("path");
const https = require("https");
const http  = require("http");
const yaml  = require("js-yaml");

// ── FILE PATHS ──────────────────────────────────────────────────
const CONFIG_YML  = "config.yml";
const HEARTBEAT   = "logs/heartbeat";
const LOGO_CACHE  = "/tmp/mitv/logo.png";

fs.mkdirSync("logs",      { recursive: true });
fs.mkdirSync("/tmp/mitv", { recursive: true });

// ── LOGGER ──────────────────────────────────────────────────────
function log(msg) {
  const line = `[${new Date().toISOString()}] ${msg}`;
  console.log(line);
  try { fs.appendFileSync("logs/stream.log", line + "\n"); } catch(_) {}
}

// ── LOAD ALL CONFIGS ────────────────────────────────────────────
function loadAll() {
  try {
    const cfg      = yaml.load(fs.readFileSync(CONFIG_YML, "utf8"));
    const playlist = JSON.parse(fs.readFileSync(cfg.files.playlist, "utf8"));
    const bar      = JSON.parse(fs.readFileSync(cfg.files.bar, "utf8"));
    log(`[CONFIG] Loaded ✓ | Playlist: ${playlist.length} items | Bar: ${bar.length} messages`);
    return { cfg, playlist, bar };
  } catch(e) {
    log(`[CONFIG] ERROR: ${e.message}`);
    return null;
  }
}

// ── FILE CHANGE WATCHER ─────────────────────────────────────────
let _mtimes = {};
function anyFileChanged(files) {
  for (const f of files) {
    try {
      const m = fs.statSync(f).mtimeMs;
      if (_mtimes[f] && _mtimes[f] !== m) { _mtimes[f] = m; return true; }
      _mtimes[f] = m;
    } catch(_) {}
  }
  return false;
}

// ── DOWNLOAD LOGO ───────────────────────────────────────────────
async function downloadLogo(url) {
  return new Promise((resolve) => {
    const file = fs.createWriteStream(LOGO_CACHE);
    const get  = url.startsWith("https") ? https.get : http.get;
    get(url, res => {
      res.pipe(file);
      file.on("finish", () => { file.close(); log("[LOGO] Downloaded ✓"); resolve(LOGO_CACHE); });
    }).on("error", e => { log(`[LOGO] Download failed: ${e.message}`); resolve(null); });
  });
}

// ── RESOLVE YOUTUBE → DIRECT URL ────────────────────────────────
async function resolveYT(url) {
  return new Promise((resolve, reject) => {
    log(`[YT-DLP] Resolving: ${url}`);
    let out = "";
    const p = spawn("yt-dlp", [
      "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
      "--get-url", "--no-playlist", url
    ]);
    p.stdout.on("data", d => (out += d));
    p.stderr.on("data", d => process.stdout.write(d));
    p.on("close", code => {
      const u = out.trim().split("\n")[0];
      if (code === 0 && u) resolve(u);
      else reject(new Error(`yt-dlp failed code=${code}`));
    });
  });
}

// ── BUILD FFMPEG FILTER COMPLEX ─────────────────────────────────
function buildFilters(cfg, barMsg, hasLogo) {
  const { stream, logo, bar, copyright: cp } = cfg;
  const W = stream.resolution.split("x")[0];
  const H = stream.resolution.split("x")[1];

  const zoom   = cp.enabled && cp.zoom_factor > 1 ? cp.zoom_factor : 1;
  const bright = cp.enabled ? (cp.brightness_adjust || 0) : 0;

  // video base chain
  let vchain = [];
  if (zoom > 1) vchain.push(`scale=iw*${zoom}:ih*${zoom},crop=iw/${zoom}:ih/${zoom}`);
  if (bright)   vchain.push(`eq=brightness=${bright}`);
  vchain.push(`scale=${W}:${H}`);

  // ticker bar
  let tickerF = "";
  if (bar.enabled && barMsg) {
    const text  = (barMsg.text || "")
      .replace(/\\/g, "\\\\")
      .replace(/'/g,  "\u2019")
      .replace(/:/g,  "\\:")
      .replace(/\[/g, "\\[")
      .replace(/\]/g, "\\]");
    const bg    = barMsg.bg_color    || "#CC0000";
    const tc    = barMsg.text_color  || "#FFFFFF";
    const bh    = bar.height         || 52;
    const fs_   = bar.font_size      || 28;
    const spd   = (bar.scroll_speed  || 3) * 60;
    const by    = bar.position === "top" ? 0 : `ih-${bh}`;
    tickerF =
      `drawbox=x=0:y=${by}:w=iw:h=${bh}:color=${bg}@0.95:t=fill,` +
      `drawtext=text='${text}':fontcolor=${tc}:fontsize=${fs_}:` +
      `y=${by}+(${bh}/2)-(text_h/2):x=w-mod(t*${spd}\\,w+tw)`;
  }

  const filters = [];

  if (hasLogo && logo.enabled) {
    const lw  = logo.width   || 140;
    const op  = logo.opacity || 0.9;
    const pos = logo.position || "top-left";
    const lx  = logo.x_offset || 20;
    const ly  = logo.y_offset || 20;
    let ox = `${lx}`, oy = `${ly}`;
    if (pos.includes("right"))  ox = `main_w-overlay_w-${lx}`;
    if (pos.includes("bottom")) oy = `main_h-overlay_h-${ly}`;

    filters.push(`[1:v]scale=${lw}:-1,format=rgba,colorchannelmixer=aa=${op}[logo]`);
    filters.push(`[0:v]${vchain.join(",")}[base]`);
    filters.push(`[base][logo]overlay=${ox}:${oy}[overlaid]`);
    if (tickerF) filters.push(`[overlaid]${tickerF}[out]`);
    else         filters.push(`[overlaid]copy[out]`);
  } else {
    filters.push(`[0:v]${vchain.join(",")}${tickerF ? "," + tickerF : ""}[out]`);
  }

  return filters.join(";");
}

// ── STREAM ONE ITEM ─────────────────────────────────────────────
function streamItem(videoUrl, cfg, barMsg, logoPath, watchFiles) {
  return new Promise((resolve, reject) => {
    const { stream, copyright: cp } = cfg;
    const hasLogo  = cfg.logo.enabled && !!logoPath;
    const filterCx = buildFilters(cfg, barMsg, hasLogo);

    // audio filter
    const pitch = cp.enabled ? (cp.audio_pitch_semitones || 0) : 0;
    let af = "aresample=44100";
    if (pitch !== 0) {
      const r = Math.pow(2, pitch / 12);
      af += `,atempo=${Math.min(Math.max(r, 0.5), 2)}`;
    }

    const inputs = ["-re", "-i", videoUrl];
    if (hasLogo) inputs.push("-i", logoPath);

    const rtmp = `${stream.rtmp_url}/${stream.youtube_stream_key}`;
    const args = [
      "-hide_banner", "-loglevel", "warning",
      ...inputs,
      "-filter_complex", filterCx,
      "-map", "[out]",
      "-map", "0:a?",
      "-af", af,
      "-c:v", "libx264", "-preset", "veryfast",
      "-b:v", stream.video_bitrate,
      "-maxrate", stream.video_bitrate,
      "-bufsize", stream.buffer_size || "5000k",
      "-g", String(stream.fps * 2),
      "-r", String(stream.fps),
      "-c:a", "aac", "-b:a", stream.audio_bitrate, "-ar", "44100",
      "-f", "flv", rtmp
    ];

    log(`[FFMPEG] → ${rtmp}`);
    const proc = spawn("ffmpeg", args, { stdio: ["ignore", "inherit", "pipe"] });
    let errBuf = "";
    proc.stderr.on("data", d => { errBuf += d; if (errBuf.length > 3000) errBuf = errBuf.slice(-3000); });

    const interval = setInterval(() => {
      fs.writeFileSync(HEARTBEAT, Date.now().toString());
      if (cfg.hot_reload.enabled && anyFileChanged(watchFiles)) {
        log("[HOT-RELOAD] Change detected → restarting stream...");
        proc.kill("SIGTERM");
      }
    }, (cfg.hot_reload.check_interval_seconds || 10) * 1000);

    proc.on("close", code => {
      clearInterval(interval);
      if (code === 0 || code === null || code === 255) resolve("done");
      else reject(new Error(`ffmpeg exit=${code} | ${errBuf.slice(-400)}`));
    });
    proc.on("error", e => { clearInterval(interval); reject(e); });
  });
}

// ── SLEEP ───────────────────────────────────────────────────────
const sleep = ms => new Promise(r => setTimeout(r, ms));

// ── MAIN 24/7 LOOP ──────────────────────────────────────────────
async function main() {
  log("================================================================");
  log("  MiTV 24/7 Live Stream Workflow — STARTING");
  log("================================================================");

  let playIdx  = 0;
  let barIdx   = 0;
  let retries  = 0;
  let logoPath = null;
  let lastData = null;

  const watchFiles = [CONFIG_YML, "playlist.json", "bar.json"];

  while (true) {
    // load / reload config
    const data = loadAll();
    if (!data) { await sleep(10000); continue; }
    lastData = data;
    const { cfg, playlist, bar } = data;

    // download logo
    if (cfg.logo.enabled && cfg.logo.url) {
      try { fs.unlinkSync(LOGO_CACHE); } catch(_) {}
      logoPath = await downloadLogo(cfg.logo.url);
    }

    const item   = playlist[playIdx % playlist.length];
    const barMsg = bar[barIdx  % bar.length];
    log(`[LOOP] [${playIdx % playlist.length + 1}/${playlist.length}] [${item.type}] ${item.title}`);

    try {
      let videoUrl = item.url;
      if (item.type === "youtube") videoUrl = await resolveYT(item.url);

      await streamItem(videoUrl, cfg, barMsg, logoPath, watchFiles);
      log("[LOOP] Item done ✓");
      retries = 0;

    } catch(e) {
      retries++;
      log(`[ERROR] (${retries}/${cfg.retry.max_per_item}) ${e.message}`);
      if (retries >= cfg.retry.max_per_item) {
        log("[SKIP] Max retries → skipping item");
        retries = 0;
        playIdx++;
      } else {
        await sleep(cfg.retry.delay_seconds * 1000);
        continue;
      }
    }

    playIdx++;
    barIdx++;
    if (playIdx >= playlist.length) {
      log("[LOOP] Playlist complete 🔁 — looping from start");
      playIdx = 0;
    }

    await sleep(1500);
  }
}

process.on("uncaughtException", async e => {
  log(`[CRASH] ${e.message} — restarting in 10s...`);
  await sleep(10000);
  main();
});
process.on("unhandledRejection", r => log(`[REJECTION] ${r}`));

main();
