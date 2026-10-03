# AGENTS.md

Working notes for AI agents (and humans) picking up this project. Read this before changing
anything; it records the things that are easy to break and hard to diagnose.

## What this is

A Flask dashboard on a Raspberry Pi Zero, shown through a fullscreen `surf` browser that LXDE
autostarts on boot. Shows a clock, three-day weather, and live TMB bus departures for line 55.
A Google Photos carousel exists but is **off by default**.

The Pi is the deployment target, not the development environment. See "Where to work" below.

## Live environment

| | |
| --- | --- |
| Pi address | `192.168.0.17` |
| SSH | `pi@192.168.0.17` (password `123`) |
| Repo on the Pi | `/home/pi/Documents/RitaFrame` |
| Browser origin | `http://127.0.0.1:8000` |
| Screen | **800x480 landscape** |
| App log on the Pi | `~/ritaframe.log` |
| GitHub | `alpoktem/RitaFrame`, branch `main` |

SSH key auth from the maintainer's Mac is already installed. For a fresh machine:

```bash
cat ~/.ssh/id_rsa.pub | ssh pi@192.168.0.17 'mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys'
```

`expect` is available if a password prompt has to be driven non-interactively.

## Where to work

**Develop on a laptop. Deploy to the Pi.** The Pi is a Zero on a slow SD card; a full boot
takes ~70 seconds before the app serves. Editing files on it and restarting to test is
materially slower than iterating locally against `python3 app.py`.

Typical loop:

```bash
# laptop
python3 app.py                    # verify on http://localhost:8000
git push origin main

# pi
cd ~/Documents/RitaFrame && git pull && ./run.sh
```

Verify on the Pi with `curl`, not by looking at the screen — SSH is faster and gives exact
values:

```bash
ssh pi@192.168.0.17 'curl -s http://127.0.0.1:8000/api/status'
```

## Rules that matter

**Never block a request.** The OAuth flow for Google Photos opens a browser and waits. It
must never run during page rendering. All photo work happens on a background thread; the
request path only reads an already-resolved URL. This was a real bug: enabling photos
originally hung `/` indefinitely on a headless Pi.

**Never fabricate data.** Bus failures render a visible error. Do not fall back to stale or
made-up arrival times, and do not add fields the TMB iBus API does not document (there is no
service-alerts method; stop-change warnings come from comparing `nom_parada` against
`bus_expected_stop_name`).

**Keep optional dependencies optional.** `photosapi` is imported lazily and `motionio`
imports `RPi.GPIO` lazily, so the dashboard runs on a non-Pi machine and without the
`google-*` packages. Do not hoist those imports to module scope.

**Config is data, not code.** Settings belong in `config.yaml`. `ConfigLoader` exposes an
mtime `version`; `Services` rebuilds itself when it changes, so no restart is needed. Service
constructors take plain values, not the loader.

**Credentials never get committed.** `credentials/*` is gitignored. TMB keys also read from
`TMB_APP_ID` / `TMB_APP_KEY`. Before committing, check that no real key material is staged.

## Pi gotchas, each of which cost real debugging time

- **The screen boots portrait.** HDMI comes up rotated 90° (480x800) despite a physically
  landscape panel. `etc/rotate-display.sh` fixes it; `runsurf.sh` calls it again so ordering
  cannot matter. `ROTATION=inverted` flips it 180°.
- **`xdotool key --window` does not work with surf.** It sends a synthetic event that surf
  ignores. The key must go through XTEST to the activated window.
- **F11 is a toggle.** Firing it blindly *un*-fullscreens an already-fullscreen window.
  Always check `_NET_WM_STATE` first.
- **surf has two windows.** One is 10x10. "Pick the largest" grabs it before the real window
  exists, so require a realistically sized window.
- **LXDE's panel and desktop stack above surf** and re-map themselves after login, so hiding
  them from a script does not hold. They are disabled in the autostart file instead.
- **`lxterminal` leaves a window behind** after its command exits, which then sits on top of
  the frame. Helper scripts are autostarted directly, without a terminal.
- **Boot needs long timeouts.** ~70s from power-on to serving. Waits default to 300s.
- **Errors must stay visible.** `surffull.sh` only tidies up *after* the browser is confirmed
  fullscreen, so a failed startup leaves the `run.sh` terminal on screen showing the error.

## Kiosk scripts must stay executable

`~/.config/lxsession/LXDE-pi/autostart` runs `runsurf.sh` and `surffull.sh` directly, so they
need mode `755` **in git**. They were once tracked as `644`, which silently skipped kiosk setup
on a fresh clone. If you add a script that autostart invokes directly, set the exec bit:

```bash
chmod +x path/to/script.sh && git update-index --chmod=+x path/to/script.sh
```

## Testing

There is no test suite. Verify with:

```bash
python3 -m py_compile *.py     # syntax
bash -n run.sh etc/surf/*.sh etc/rotate-display.sh   # shell syntax
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8000/   # routes
curl -s http://127.0.0.1:8000/api/status                         # feature flags + health
```

`/api/status` is the quickest confirmation that a change did not break a feature: it reports
the active view, which views exist, per-feature enable flags, bus health, and photo status.

Expected: `/`, `/view/clock`, `/api/*` return 200; `/view/<unknown>` returns 404.

## Style

Comments should explain **why**, not restate the code. Several comments in this repo are long
because they record a specific bug that was fixed — keep that context when editing nearby
lines, and do not delete it as redundant.

Commit messages describe the problem and the fix, not the files touched. Reference the Pi
behaviour when that is what makes the change non-obvious.

## Planned work

Not started. In rough order of intent:

- **Flip the frame 180°** so the cable input sits at the bottom. `ROTATION=inverted` in
  `etc/rotate-display.sh`, then confirm with `xrandr | head -2`.
- **Investigate the light sensor.** There is *no* light-sensor code in this project and none
  is configured, so any sensor fitted is currently doing nothing. Treat the wiring and part
  type as unknown — establish those before writing any driver code. Likely goal is dimming the
  screen at night.
- **New visual design**, built on a laptop first, involving images and animation. Design for
  800x480 landscape and keep the animation cheap enough for a Zero. Splitting the inline CSS/JS
  in `templates/` into `static/` is likely part of this.

## Reference

- TMB iBus: <https://developer.tmb.cat/api-docs/v1/ibus> — one method, arrivals for a stop.
- Stop `789` is `Pg de l'Exposició - Santa Madrona`, served by line 55 toward Parc de Montjuïc.
- The current Google Photos OAuth client is dead (`deleted_client`), so photos need a fresh
  client plus a one-off `/photos/auth` login before they will load.
