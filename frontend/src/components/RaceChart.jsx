import { useEffect, useRef } from "react";
import {
  Chart,
  LineController,
  LineElement,
  PointElement,
  LinearScale,
  Title,
  Tooltip,
} from "chart.js";

Chart.register(LineController, LineElement, PointElement, LinearScale, Title, Tooltip);

export const MY_COLOR = "#00ff88";
export const THEM_COLOR = "#ff3c6e";

/**
 * Runtime vs input size for both players.
 *
 * The chart is kept in a ref and updated in place. Results come in one player
 * at a time, so recreating it on each message would wipe the other curve.
 */
export default function RaceChart({ players, series, placeholder }) {
  const canvasRef = useRef(null);
  const chartRef = useRef(null);

  useEffect(() => {
    const chart = new Chart(canvasRef.current.getContext("2d"), {
      type: "line",
      data: {
        datasets: [MY_COLOR, THEM_COLOR].map((color) => ({
          data: [],
          borderColor: color,
          backgroundColor: "transparent",
          pointBackgroundColor: color,
          tension: 0.3,
        })),
      },
      options: {
        animation: false,
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: {
            type: "linear",
            title: {
              display: true,
              text: "Input Size (n)",
              color: "#6b6b8a",
              font: { family: "'Space Mono'" },
            },
            grid: { color: "rgba(255,255,255,0.05)" },
            ticks: { color: "#6b6b8a" },
          },
          y: {
            title: {
              display: true,
              text: "Time (ms)",
              color: "#6b6b8a",
              font: { family: "'Space Mono'" },
            },
            grid: { color: "rgba(255,255,255,0.05)" },
            ticks: { color: "#6b6b8a" },
          },
        },
      },
    });
    chartRef.current = chart;
    return () => {
      chart.destroy();
      chartRef.current = null;
    };
  }, []);

  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;
    players.forEach((name, i) => {
      chart.data.datasets[i].label = name;
      chart.data.datasets[i].data = series[name] ?? [];
    });
    chart.update();
  }, [players, series]);

  return (
    <>
      <div className="chart-wrap">
        <canvas ref={canvasRef} />
        {placeholder && (
          <div className="chart-placeholder">
            <div className="chart-placeholder-icon">📊</div>
            <p>Chart appears after both players submit</p>
          </div>
        )}
      </div>
      <div className="race-legend">
        {players.map((name, i) => (
          <div className="legend-item" key={name || i}>
            <div
              className="legend-dot"
              style={{ background: i === 0 ? MY_COLOR : THEM_COLOR }}
            />
            <span>{name}</span>
          </div>
        ))}
      </div>
    </>
  );
}
