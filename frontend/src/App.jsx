import { useCallback, useEffect, useRef, useState } from "react";

import { api, wsUrl } from "./api.js";
import { useAuth } from "./hooks/useAuth.js";
import { useBattleRoom } from "./hooks/useBattleRoom.js";
import MatchmakingOverlay from "./components/MatchmakingOverlay.jsx";
import AuthScreen from "./screens/AuthScreen.jsx";
import BattleScreen from "./screens/BattleScreen.jsx";
import LobbyScreen from "./screens/LobbyScreen.jsx";
import SoloScreen from "./screens/SoloScreen.jsx";
import TournamentScreen from "./screens/TournamentScreen.jsx";
import WaitingScreen from "./screens/WaitingScreen.jsx";

const EMPTY_TOURNAMENT = {
  players: [],
  bracket: [],
  status: "lobby",
  host: null,
  winner: null,
  roundLabel: null,
};

export default function App() {
  const { session, checking, save, clear } = useAuth();

  const [screen, setScreen] = useState("lobby");
  const [battle, setBattle] = useState(null); // {roomCode, problem}
  const [matchmaking, setMatchmaking] = useState(null);
  const [tournamentCode, setTournamentCode] = useState(null);
  const [tournament, setTournament] = useState(EMPTY_TOURNAMENT);

  const queueSocketRef = useRef(null);
  const tournamentSocketRef = useRef(null);

  const token = session?.token ?? null;
  const username = session?.username ?? null;

  const room = useBattleRoom(battle?.roomCode ?? null, token);

  // Both players are in, so move to the arena. The delay lets the waiting
  // screen show the opponent's name first.
  useEffect(() => {
    if (screen !== "waiting" || room.players.length < 2) return undefined;
    const t = setTimeout(() => setScreen("battle"), 800);
    return () => clearTimeout(t);
  }, [screen, room.players.length]);

  const enterRoom = useCallback(async (roomCode) => {
    const data = await api.room(roomCode);
    if (data.error) throw new Error(data.error);
    setBattle({ roomCode, problem: data.problem });
    setScreen("waiting");
  }, []);

  // ── Lobby actions ──────────────────────────────────────────────────────────

  const createRoom = useCallback(
    async (problemId) => {
      const data = await api.createRoom(problemId, token);
      setBattle({ roomCode: data.room_code, problem: data.problem });
      setScreen("waiting");
    },
    [token]
  );

  const leaveBattle = useCallback(() => {
    setBattle(null);
    setScreen(tournamentCode ? "tournament" : "lobby");
  }, [tournamentCode]);

  // ── Matchmaking ────────────────────────────────────────────────────────────

  const cancelMatchmaking = useCallback(() => {
    const socket = queueSocketRef.current;
    if (socket) {
      try {
        socket.send(JSON.stringify({ type: "cancel" }));
      } catch {
        /* already closing */
      }
      socket.close();
      queueSocketRef.current = null;
    }
    setMatchmaking(null);
  }, []);

  const findMatch = useCallback(() => {
    setMatchmaking({ status: "Connecting..." });
    const socket = new WebSocket(wsUrl("/ws/queue", token));
    queueSocketRef.current = socket;

    socket.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      if (msg.type === "searching") {
        setMatchmaking({
          status: "Searching for opponent...",
          elo: msg.elo,
          queueSize: msg.queue_size,
        });
      } else if (msg.type === "still_searching") {
        setMatchmaking((prev) => ({ ...prev, queueSize: msg.queue_size }));
      } else if (msg.type === "matched") {
        queueSocketRef.current = null;
        setMatchmaking(null);
        enterRoom(msg.room_code).catch(() => setMatchmaking(null));
      }
    };
    socket.onerror = () =>
      setMatchmaking({ status: "Connection error — is the server running?" });
    socket.onclose = () => {
      queueSocketRef.current = null;
      setMatchmaking((prev) => (prev ? null : prev));
    };
  }, [token, enterRoom]);

  // ── Tournament ─────────────────────────────────────────────────────────────

  const leaveTournament = useCallback(() => {
    const socket = tournamentSocketRef.current;
    if (socket) {
      socket.onclose = null;
      socket.close();
      tournamentSocketRef.current = null;
    }
    setTournamentCode(null);
    setTournament(EMPTY_TOURNAMENT);
    setBattle(null);
    setScreen("lobby");
  }, []);

  const joinTournament = useCallback(
    (code) => {
      setTournamentCode(code);
      setTournament(EMPTY_TOURNAMENT);
      setScreen("tournament");

      const socket = new WebSocket(wsUrl(`/ws/tournament/${code}`, token));
      tournamentSocketRef.current = socket;

      socket.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        switch (msg.type) {
          case "lobby_state":
            setTournament((p) => ({
              ...p,
              players: msg.players,
              host: msg.host,
              status: msg.status,
            }));
            break;
          case "player_joined":
          case "player_left":
            setTournament((p) => ({ ...p, players: msg.players }));
            break;
          case "tournament_started":
            setTournament((p) => ({ ...p, status: "active" }));
            break;
          case "round_start":
            setTournament((p) => ({
              ...p,
              bracket: msg.bracket,
              roundLabel: `Round ${msg.round} — ${msg.problem_title}`,
            }));
            break;
          case "round_done":
            setTournament((p) => ({
              ...p,
              bracket: msg.bracket,
              roundLabel: `Round ${msg.round} complete`,
            }));
            break;
          case "match_ready":
            // The tournament assigns this player a room; drop straight in.
            enterRoom(msg.room_code).catch(() => {});
            break;
          case "tournament_done":
            setTournament((p) => ({ ...p, bracket: msg.bracket, winner: msg.winner }));
            break;
          default:
            break;
        }
      };
      socket.onclose = () => {
        tournamentSocketRef.current = null;
      };
    },
    [token, enterRoom]
  );

  const hostTournament = useCallback(async () => {
    const data = await api.createTournament(username, token);
    joinTournament(data.tournament_code);
  }, [username, token, joinTournament]);

  const startTournament = useCallback(() => {
    tournamentSocketRef.current?.send(JSON.stringify({ type: "start" }));
  }, []);

  // Close both sockets when the app unmounts or the user logs out.
  useEffect(
    () => () => {
      queueSocketRef.current?.close();
      tournamentSocketRef.current?.close();
    },
    []
  );

  const logout = useCallback(() => {
    cancelMatchmaking();
    leaveTournament();
    clear();
  }, [cancelMatchmaking, leaveTournament, clear]);

  // ── Render ─────────────────────────────────────────────────────────────────

  if (checking) return null;
  if (!session) return <AuthScreen onAuthenticated={save} />;

  return (
    <>
      {screen === "lobby" && (
        <LobbyScreen
          username={username}
          onLogout={logout}
          onCreateRoom={createRoom}
          onJoinRoom={enterRoom}
          onSolo={() => setScreen("solo")}
          onFindMatch={findMatch}
          onHostTournament={hostTournament}
          onJoinTournament={joinTournament}
        />
      )}

      {screen === "solo" && <SoloScreen token={token} onBack={() => setScreen("lobby")} />}

      {screen === "waiting" && battle && (
        <WaitingScreen
          roomCode={battle.roomCode}
          problem={battle.problem}
          players={room.players}
          you={username}
        />
      )}

      {screen === "battle" && battle && (
        <BattleScreen
          you={username}
          problem={battle.problem}
          players={room.players}
          room={room}
          token={token}
          rematchLabel={tournamentCode ? "Back to Bracket" : "Rematch"}
          onRematch={leaveBattle}
          onLeave={tournamentCode ? leaveTournament : leaveBattle}
        />
      )}

      {screen === "tournament" && tournamentCode && (
        <TournamentScreen
          code={tournamentCode}
          you={username}
          state={tournament}
          onStart={startTournament}
          onLeave={leaveTournament}
        />
      )}

      {matchmaking && (
        <MatchmakingOverlay
          status={matchmaking.status}
          elo={matchmaking.elo}
          queueSize={matchmaking.queueSize}
          onCancel={cancelMatchmaking}
        />
      )}
    </>
  );
}
