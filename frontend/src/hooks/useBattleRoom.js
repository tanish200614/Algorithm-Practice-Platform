import { useCallback, useEffect, useRef, useState } from "react";

import { wsUrl } from "../api.js";

const EMPTY = {
  players: [],
  status: "waiting",
  results: {},
  raceInfo: null,
  readyNote: null,
  error: null,
};

/**
 * Owns the battle room WebSocket.
 *
 * Results come in per player, so `results` is keyed by name and merged as each
 * message arrives. Otherwise your results would overwrite the opponent's curve.
 */
export function useBattleRoom(roomCode, token) {
  const [state, setState] = useState(EMPTY);
  const socketRef = useRef(null);

  useEffect(() => {
    if (!roomCode) return undefined;

    setState(EMPTY);
    const socket = new WebSocket(wsUrl(`/ws/${roomCode}`, token));
    socketRef.current = socket;

    socket.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      setState((prev) => {
        switch (msg.type) {
          case "joined":
            return { ...prev, players: msg.players ?? [], status: msg.room_status };
          case "player_joined":
          case "player_left":
            return { ...prev, players: msg.players ?? [] };
          case "player_ready":
            return {
              ...prev,
              readyNote: `${msg.player} submitted (${msg.ready_count}/${msg.total})`,
            };
          case "race_start":
            return { ...prev, status: "racing", readyNote: null };
          case "results":
            return {
              ...prev,
              results: { ...prev.results, [msg.player]: { ...msg.data, language: msg.language } },
            };
          case "race_done":
            return { ...prev, status: "done", raceInfo: msg };
          case "error":
            return { ...prev, error: msg.msg };
          default:
            return prev;
        }
      });
    };

    socket.onerror = () =>
      setState((prev) => ({ ...prev, error: "Connection error — is the server running?" }));

    return () => {
      socket.onmessage = null;
      socket.onerror = null;
      socket.close();
      socketRef.current = null;
    };
  }, [roomCode, token]);

  const submit = useCallback((code, language) => {
    const socket = socketRef.current;
    if (socket?.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({ type: "submit", code, language }));
    }
  }, []);

  return { ...state, submit };
}
