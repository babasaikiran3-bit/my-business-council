#!/bin/bash
# LLM Council — control de servicios (start/stop/status/restart/logs)
# Uso: council {start|stop|restart|status|logs} [--no-open]

DIR="/home/andres/llm-council"
RUN="$DIR/data/run"
BACK_PID="$RUN/backend.pid"
FRONT_PID="$RUN/frontend.pid"
BACK_LOG="$RUN/backend.log"
FRONT_LOG="$RUN/frontend.log"
BACK_URL="http://localhost:8001"
FRONT_URL="http://localhost:5173"

mkdir -p "$RUN"

_alive() { [ -f "$1" ] && kill -0 "$(cat "$1")" 2>/dev/null; }
_back_up() { curl -fs "$BACK_URL/" >/dev/null 2>&1; }
_front_up() { curl -fs "$FRONT_URL/" >/dev/null 2>&1; }

# Mata el grupo de procesos del pidfile (setsid => el pid es líder de grupo).
_kill_pidfile() {
  local pf="$1"
  [ -f "$pf" ] || return 0
  local pid; pid="$(cat "$pf")"
  if kill -0 "$pid" 2>/dev/null; then
    kill -TERM -- "-$pid" 2>/dev/null || kill -TERM "$pid" 2>/dev/null
    sleep 1
    kill -0 "$pid" 2>/dev/null && kill -KILL -- "-$pid" 2>/dev/null
  fi
  rm -f "$pf"
}

start() {
  if _back_up && _front_up; then
    echo "✓ Ya está corriendo  ($FRONT_URL)"; return 0
  fi

  if ! _back_up; then
    echo "→ Backend en $BACK_URL …"
    ( cd "$DIR" && setsid uv run python -m backend.main >"$BACK_LOG" 2>&1 < /dev/null & echo $! > "$BACK_PID" )
  else
    echo "  backend ya respondía, lo reutilizo"
  fi

  if ! _front_up; then
    echo "→ Frontend en $FRONT_URL …"
    ( cd "$DIR/frontend" && setsid npm run dev >"$FRONT_LOG" 2>&1 < /dev/null & echo $! > "$FRONT_PID" )
  else
    echo "  frontend ya respondía, lo reutilizo"
  fi

  # Esperar a que el backend responda (hasta ~20s)
  for _ in $(seq 1 20); do _back_up && break; sleep 1; done
  if _back_up; then echo "✓ Backend OK"; else echo "⚠ El backend no respondió; ver: council logs"; fi

  if [ "$1" != "--no-open" ]; then
    sleep 1; command -v xdg-open >/dev/null && xdg-open "$FRONT_URL" >/dev/null 2>&1 &
  fi
  echo "✓ LLM Council levantado → $FRONT_URL"
}

stop() {
  echo "→ Apagando…"
  _kill_pidfile "$FRONT_PID"
  _kill_pidfile "$BACK_PID"
  # Fallback: por si quedó algo fuera de los pidfiles
  pkill -f "backend.main" 2>/dev/null
  pkill -f "$DIR/frontend/node_modules/.bin/vite" 2>/dev/null
  sleep 1
  echo "✓ Detenido"
}

status() {
  if _back_up; then echo "● backend  : UP    ($BACK_URL)"; else echo "○ backend  : DOWN"; fi
  if _front_up; then echo "● frontend : UP    ($FRONT_URL)"; else echo "○ frontend : DOWN"; fi
}

logs() {
  echo "== logs (Ctrl+C para salir) =="
  tail -n 40 -f "$BACK_LOG" "$FRONT_LOG"
}

case "$1" in
  start)   start "$2" ;;
  stop)    stop ;;
  restart) stop; sleep 1; start "$2" ;;
  status)  status ;;
  logs)    logs ;;
  *) echo "Uso: council {start|stop|restart|status|logs} [--no-open]" ;;
esac
