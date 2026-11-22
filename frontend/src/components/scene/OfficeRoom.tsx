import { Html, RoundedBox } from "@react-three/drei";
import type { AgentState, BugItem } from "../../types";
import {
  BUG_BOARD_POS,
  CORE_ROLES,
  DESK_LAYOUT,
  getStatusColor,
  ROOM_DOORS,
} from "./officeLayout";

interface OfficeRoomProps {
  agents: Record<string, AgentState>;
  bugs: BugItem[];
  onSelectAgent: (agentId: string, focusPos: [number, number, number]) => void;
  onOpenBugBoard: () => void;
}

/** Frameless modern tempered-glass partition with warm cream plinth and slim charcoal-aluminum channels. */
function GlassPartition({
  position,
  size,
}: {
  position: [number, number, number];
  size: [number, number, number];
}) {
  const [w, h, d] = size;
  const baseH = 0.38;
  const glassH = Math.max(0.25, h - baseH - 0.05);

  return (
    <group position={position}>
      {/* Plain Matte-Cream Baseboard */}
      <mesh position={[0, baseH / 2, 0]}>
        <boxGeometry args={[w, baseH, d]} />
        <meshStandardMaterial color="#e8dfd0" roughness={0.62} />
      </mesh>
      {/* Slim Matte-Charcoal Aluminum Base & Top Channels */}
      <mesh position={[0, baseH + 0.015, 0]}>
        <boxGeometry args={[w + 0.01, 0.03, d * 0.7]} />
        <meshStandardMaterial color="#475569" metalness={0.45} roughness={0.35} />
      </mesh>
      <mesh position={[0, h - 0.018, 0]}>
        <boxGeometry args={[w + 0.01, 0.035, d * 0.7]} />
        <meshStandardMaterial color="#475569" metalness={0.45} roughness={0.35} />
      </mesh>
      {/* Clear Tempered Architectural Glass */}
      <mesh position={[0, baseH + glassH / 2 + 0.015, 0]}>
        <boxGeometry args={[w, glassH, Math.max(0.02, d * 0.35)]} />
        <meshStandardMaterial
          color="#dbeafe"
          transparent
          opacity={0.18}
          roughness={0.12}
          metalness={0.05}
        />
      </mesh>
    </group>
  );
}

function RoomDoorway({
  position,
  doorWidth = 2.0,
  roomCode,
  title,
  accentColor,
}: {
  position: [number, number, number];
  doorWidth?: number;
  roomCode: string;
  title: string;
  accentColor: string;
}) {
  const doorHeight = 2.35;
  const half = doorWidth / 2;

  return (
    <group position={position}>
      {/* Brushed Aluminum Threshold */}
      <mesh position={[0, 0.012, 0]}>
        <boxGeometry args={[doorWidth + 0.1, 0.02, 0.14]} />
        <meshStandardMaterial color="#94a3b8" metalness={0.45} roughness={0.35} />
      </mesh>
      {/* Slim Matte-Charcoal Aluminum Door Jambs */}
      {[-half, half].map((jx, idx) => (
        <mesh key={idx} position={[jx, doorHeight / 2, 0]}>
          <boxGeometry args={[0.05, doorHeight, 0.09]} />
          <meshStandardMaterial color="#475569" metalness={0.45} roughness={0.35} />
        </mesh>
      ))}
      {/* Clean Transom Aluminum Header & Accent Light Strip */}
      <mesh position={[0, doorHeight - 0.04, 0]}>
        <boxGeometry args={[doorWidth + 0.08, 0.08, 0.09]} />
        <meshStandardMaterial color="#475569" metalness={0.45} roughness={0.35} />
      </mesh>
      <mesh position={[0, doorHeight - 0.09, 0.03]}>
        <boxGeometry args={[doorWidth - 0.14, 0.018, 0.02]} />
        <meshBasicMaterial color={accentColor} />
      </mesh>

      {/* Architectural Room Code Sign */}
      <Html position={[0, 2.52, 0]} center distanceFactor={16} zIndexRange={[10, 0]}>
        <div
          style={{
            background: "rgba(255,252,245,0.96)",
            border: `1.5px solid ${accentColor}`,
            color: "#0f172a",
            padding: "3px 10px",
            borderRadius: 999,
            fontSize: 10,
            fontWeight: 800,
            letterSpacing: "0.04em",
            whiteSpace: "nowrap",
            boxShadow: "0 4px 12px rgba(15,23,42,0.12)",
            pointerEvents: "none",
          }}
        >
          <span style={{ color: accentColor, marginRight: 5 }}>{roomCode}</span>
          {title}
        </div>
      </Html>
    </group>
  );
}

function OfficePlant({
  position,
  scale = 1,
}: {
  position: [number, number, number];
  scale?: number;
}) {
  return (
    <group position={position} scale={scale}>
      <mesh position={[0, 0.2, 0]}>
        <cylinderGeometry args={[0.2, 0.15, 0.4, 16]} />
        <meshStandardMaterial color="#475569" roughness={0.5} />
      </mesh>
      <mesh position={[0, 0.4, 0]}>
        <cylinderGeometry args={[0.175, 0.175, 0.03, 16]} />
        <meshStandardMaterial color="#334155" roughness={0.85} />
      </mesh>
      <mesh position={[0, 0.65, 0]}>
        <sphereGeometry args={[0.24, 14, 12]} />
        <meshStandardMaterial color="#16a34a" roughness={0.75} />
      </mesh>
      <mesh position={[0.13, 0.86, -0.05]}>
        <sphereGeometry args={[0.16, 12, 10]} />
        <meshStandardMaterial color="#22c55e" roughness={0.75} />
      </mesh>
      <mesh position={[-0.13, 0.82, 0.07]}>
        <sphereGeometry args={[0.15, 12, 10]} />
        <meshStandardMaterial color="#15803d" roughness={0.75} />
      </mesh>
    </group>
  );
}

function LoungeChair({
  position,
  rotationY = 0,
  fabricColor = "#c2410c",
}: {
  position: [number, number, number];
  rotationY?: number;
  fabricColor?: string;
}) {
  return (
    <group position={position} rotation={[0, rotationY, 0]}>
      <mesh position={[0, 0.22, 0]}>
        <cylinderGeometry args={[0.04, 0.18, 0.36, 12]} />
        <meshStandardMaterial color="#334155" metalness={0.5} roughness={0.35} />
      </mesh>
      <RoundedBox args={[0.48, 0.08, 0.46]} radius={0.03} position={[0, 0.44, 0]}>
        <meshStandardMaterial color={fabricColor} roughness={0.72} />
      </RoundedBox>
      <RoundedBox args={[0.46, 0.38, 0.07]} radius={0.03} position={[0, 0.65, -0.2]}>
        <meshStandardMaterial color={fabricColor} roughness={0.72} />
      </RoundedBox>
    </group>
  );
}

function Workstation({
  spec,
  agent,
  onSelect,
}: {
  spec: (typeof DESK_LAYOUT)["leader"];
  agent: AgentState | undefined;
  onSelect: () => void;
}) {
  const isLeader = spec.role === "leader";
  const isActive =
    agent?.status === "working_ai" || agent?.status === "working_offline";
  const statusColor = agent ? getStatusColor(agent.status) : "#64748b";
  const screenGlow = isActive
    ? agent?.execution_kind === "offline"
      ? "#10b981"
      : "#38bdf8"
    : "#93c5fd";

  const deskWidth = isLeader ? 2.0 : 1.56;
  const deskDepth = isLeader ? 0.9 : 0.78;

  return (
    <group
      position={spec.deskPos}
      rotation={[0, spec.deskRotationY, 0]}
      onClick={(e) => {
        e.stopPropagation();
        onSelect();
      }}
    >
      {/* High-Contrast Dark Charcoal-Navy / Slate Desktop against Warm Cream Walls */}
      <RoundedBox args={[deskWidth, 0.048, deskDepth]} radius={0.018} position={[0, 0.74, 0]}>
        <meshStandardMaterial
          color={isLeader ? "#1e293b" : "#334155"}
          roughness={0.35}
        />
      </RoundedBox>

      {/* Matte Dark Steel Slim Legs */}
      {[
        [-deskWidth / 2 + 0.1, -deskDepth / 2 + 0.08],
        [deskWidth / 2 - 0.1, -deskDepth / 2 + 0.08],
        [-deskWidth / 2 + 0.1, deskDepth / 2 - 0.08],
        [deskWidth / 2 - 0.1, deskDepth / 2 - 0.08],
      ].map(([lx, lz], idx) => (
        <mesh key={idx} position={[lx, 0.36, lz]}>
          <cylinderGeometry args={[0.022, 0.022, 0.72, 10]} />
          <meshStandardMaterial color="#1e293b" metalness={0.55} roughness={0.3} />
        </mesh>
      ))}

      {/* Warm Camel Desk Pad + Light Keyboard & Mouse */}
      <mesh position={[0, 0.768, -0.18]}>
        <boxGeometry args={[0.64, 0.006, 0.26]} />
        <meshStandardMaterial color="#d6c7b2" roughness={0.7} />
      </mesh>
      <mesh position={[-0.04, 0.778, -0.18]}>
        <boxGeometry args={[0.36, 0.012, 0.12]} />
        <meshStandardMaterial color="#f8fafc" roughness={0.35} />
      </mesh>
      <mesh position={[0.22, 0.778, -0.18]}>
        <boxGeometry args={[0.055, 0.014, 0.09]} />
        <meshStandardMaterial color="#e2e8f0" roughness={0.35} />
      </mesh>

      {/* Side-Angled Slim Monitor on the Right Corner (Keeps Center Sightline 100% Open!) */}
      <group position={[0.5, 0.94, 0.14]} rotation={[0, Math.PI - 0.42, 0]}>
        <mesh position={[0, -0.14, -0.02]}>
          <boxGeometry args={[0.05, 0.16, 0.04]} />
          <meshStandardMaterial color="#94a3b8" metalness={0.55} roughness={0.3} />
        </mesh>
        <mesh position={[0, -0.18, 0.02]}>
          <boxGeometry args={[0.22, 0.014, 0.14]} />
          <meshStandardMaterial color="#94a3b8" metalness={0.55} roughness={0.3} />
        </mesh>
        <RoundedBox args={[0.68, 0.34, 0.024]} radius={0.012}>
          <meshStandardMaterial color="#0f172a" roughness={0.25} />
        </RoundedBox>
        <mesh position={[0, 0, 0.014]}>
          <planeGeometry args={[0.63, 0.29]} />
          <meshBasicMaterial color={screenGlow} />
        </mesh>
      </group>

      {/* Compact Matte Tablet / Notebook on Left Side */}
      <RoundedBox
        args={[0.28, 0.014, 0.2]}
        radius={0.006}
        position={[-0.36, 0.774, 0.14]}
        rotation={[0, 0.2, 0]}
      >
        <meshStandardMaterial color="#cbd5e1" roughness={0.35} />
      </RoundedBox>

      {/* Coffee Mug */}
      <mesh position={[-deskWidth / 2 + 0.18, 0.8, -0.14]}>
        <cylinderGeometry args={[0.036, 0.032, 0.085, 12]} />
        <meshStandardMaterial color={spec.shirtColor} roughness={0.35} />
      </mesh>

      {/* Modern High-Contrast Ergonomic Chair behind Desk */}
      <group position={[0, 0, -0.66]}>
        <mesh position={[0, 0.22, 0]}>
          <cylinderGeometry args={[0.032, 0.032, 0.38, 10]} />
          <meshStandardMaterial color="#1e293b" metalness={0.5} />
        </mesh>
        <mesh position={[0, 0.04, 0]}>
          <cylinderGeometry args={[0.25, 0.25, 0.035, 16]} />
          <meshStandardMaterial color="#1e293b" metalness={0.4} />
        </mesh>
        <RoundedBox args={[0.5, 0.08, 0.46]} radius={0.03} position={[0, 0.43, 0]}>
          <meshStandardMaterial
            color={isLeader ? "#1d4ed8" : "#0f766e"}
            roughness={0.68}
          />
        </RoundedBox>
        <RoundedBox args={[0.46, 0.56, 0.065]} radius={0.03} position={[0, 0.75, -0.2]}>
          <meshStandardMaterial
            color={isLeader ? "#1d4ed8" : "#0f766e"}
            roughness={0.65}
          />
        </RoundedBox>
      </group>

      {/* Glowing Status Pill */}
      <mesh position={[-deskWidth / 2 + 0.12, 0.78, deskDepth / 2 - 0.1]}>
        <sphereGeometry args={[0.042, 12, 10]} />
        <meshBasicMaterial color={statusColor} />
      </mesh>
    </group>
  );
}

function FigmaMoodboard({ position }: { position: [number, number, number] }) {
  return (
    <group position={position}>
      <RoundedBox args={[2.1, 1.25, 0.05]} radius={0.025}>
        <meshStandardMaterial color="#ffffff" roughness={0.32} />
      </RoundedBox>
      {/* Slim Matte-Slate Outer Frame */}
      <mesh position={[0, 0, -0.015]}>
        <boxGeometry args={[2.16, 1.31, 0.02]} />
        <meshStandardMaterial color="#334155" metalness={0.45} roughness={0.35} />
      </mesh>
      {[
        { x: -0.68, y: 0.28, c: "#3b82f6" },
        { x: -0.22, y: 0.28, c: "#10b981" },
        { x: 0.24, y: 0.28, c: "#f59e0b" },
        { x: 0.7, y: 0.28, c: "#ec4899" },
      ].map((sw, i) => (
        <mesh key={i} position={[sw.x, sw.y, 0.03]}>
          <boxGeometry args={[0.34, 0.34, 0.012]} />
          <meshStandardMaterial color={sw.c} roughness={0.4} />
        </mesh>
      ))}
      <mesh position={[0, -0.26, 0.03]}>
        <boxGeometry args={[1.82, 0.42, 0.012]} />
        <meshStandardMaterial color="#f1f5f9" roughness={0.5} />
      </mesh>
      <Html position={[0, 0.78, 0.05]} center distanceFactor={15} zIndexRange={[10, 0]}>
        <div
          style={{
            background: "#0f172a",
            color: "#e2e8f0",
            padding: "2px 9px",
            borderRadius: 999,
            fontSize: 9,
            fontWeight: 700,
            whiteSpace: "nowrap",
            pointerEvents: "none",
          }}
        >
          🎨 Figma Design Tokens
        </div>
      </Html>
    </group>
  );
}

function CompactServerRack({ position }: { position: [number, number, number] }) {
  return (
    <group position={position}>
      <RoundedBox args={[0.68, 1.85, 0.62]} radius={0.04} position={[0, 0.925, 0]}>
        <meshStandardMaterial color="#1e293b" metalness={0.55} roughness={0.35} />
      </RoundedBox>
      {[0.38, 0.66, 0.94, 1.22, 1.5].map((y, idx) => (
        <group key={idx} position={[0, y, 0.315]}>
          <mesh>
            <boxGeometry args={[0.54, 0.16, 0.02]} />
            <meshStandardMaterial color="#334155" roughness={0.45} />
          </mesh>
          <mesh position={[-0.2, 0, 0.015]}>
            <sphereGeometry args={[0.018, 8, 8]} />
            <meshBasicMaterial color={idx % 2 === 0 ? "#22c55e" : "#38bdf8"} />
          </mesh>
          <mesh position={[0.18, 0, 0.015]}>
            <sphereGeometry args={[0.015, 8, 8]} />
            <meshBasicMaterial color="#0ea5e9" />
          </mesh>
        </group>
      ))}
    </group>
  );
}

function BugBoard3D({
  bugs,
  onClick,
}: {
  bugs: BugItem[];
  onClick: () => void;
}) {
  const pendingCount = bugs.filter(
    (b) => b.status === "pending_review" || b.status === "still_failing"
  ).length;
  const fixedCount = bugs.filter((b) => b.status === "fixed").length;

  return (
    <group
      position={BUG_BOARD_POS}
      rotation={[0, -Math.PI / 2, 0]}
      onClick={(e) => {
        e.stopPropagation();
        onClick();
      }}
    >
      <RoundedBox args={[2.3, 1.38, 0.08]} radius={0.03}>
        <meshStandardMaterial color="#ffffff" roughness={0.28} />
      </RoundedBox>
      {/* Matte Slate Outer Frame */}
      <mesh position={[0, 0, -0.02]}>
        <boxGeometry args={[2.4, 1.48, 0.045]} />
        <meshStandardMaterial color="#334155" metalness={0.45} roughness={0.35} />
      </mesh>
      {/* Top Status Bar */}
      <mesh position={[0, 0.56, 0.045]}>
        <boxGeometry args={[2.1, 0.12, 0.015]} />
        <meshBasicMaterial color={pendingCount > 0 ? "#f59e0b" : "#10b981"} />
      </mesh>
      {/* Visual Bug Ticket Sticky Cards */}
      {[-0.65, 0, 0.65].map((x, idx) => (
        <mesh key={idx} position={[x, 0.06, 0.045]}>
          <boxGeometry args={[0.52, 0.64, 0.015]} />
          <meshStandardMaterial
            color={
              idx < pendingCount ? "#fef3c7" : fixedCount > 0 ? "#dcfce7" : "#f1f5f9"
            }
            roughness={0.5}
          />
        </mesh>
      ))}

      <Html position={[0, 0.96, 0.08]} center distanceFactor={14} zIndexRange={[10, 0]}>
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onClick();
          }}
          style={{
            background: pendingCount > 0 ? "#d97706" : "#0f172a",
            color: "#ffffff",
            border: "1.5px solid rgba(255,255,255,0.65)",
            padding: "4px 11px",
            borderRadius: 999,
            fontSize: 11,
            fontWeight: 700,
            cursor: "pointer",
            whiteSpace: "nowrap",
            boxShadow: "0 4px 12px rgba(0,0,0,0.22)",
          }}
        >
          📌 Bug Board{" "}
          {pendingCount > 0
            ? `(${pendingCount} chờ duyệt)`
            : fixedCount > 0
              ? `(✅ ${fixedCount} sạch)`
              : "(0 lỗi)"}
        </button>
      </Html>
    </group>
  );
}

function EspressoBar({ position }: { position: [number, number, number] }) {
  return (
    <group position={position}>
      {/* Deep Forest-Teal Counter Base & Warm Quartz Countertop */}
      <RoundedBox args={[2.2, 0.96, 0.68]} radius={0.04} position={[0, 0.48, 0]}>
        <meshStandardMaterial color="#115e59" roughness={0.45} />
      </RoundedBox>
      <RoundedBox args={[2.32, 0.07, 0.78]} radius={0.025} position={[0, 0.99, 0]}>
        <meshStandardMaterial color="#faf5ec" roughness={0.22} />
      </RoundedBox>
      {/* Espresso Machine */}
      <RoundedBox args={[0.48, 0.4, 0.34]} radius={0.03} position={[-0.5, 1.23, 0]}>
        <meshStandardMaterial color="#1e293b" metalness={0.65} roughness={0.25} />
      </RoundedBox>
      {/* Matcha Canisters */}
      <mesh position={[0.05, 1.13, 0]}>
        <cylinderGeometry args={[0.08, 0.08, 0.2, 12]} />
        <meshStandardMaterial color="#10b981" roughness={0.35} />
      </mesh>
      <mesh position={[0.26, 1.11, 0]}>
        <cylinderGeometry args={[0.075, 0.075, 0.16, 12]} />
        <meshStandardMaterial color="#f59e0b" roughness={0.35} />
      </mesh>
      {/* Glass Pastry Dome */}
      <mesh position={[0.68, 1.14, 0]}>
        <sphereGeometry args={[0.17, 16, 12, 0, Math.PI * 2, 0, Math.PI / 2]} />
        <meshStandardMaterial color="#e0f2fe" transparent opacity={0.42} roughness={0.12} />
      </mesh>
    </group>
  );
}

function SofaTvLounge({ position }: { position: [number, number, number] }) {
  return (
    <group position={position}>
      {/* Warm Taupe Rug */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.012, 0.55]}>
        <planeGeometry args={[3.5, 2.5]} />
        <meshStandardMaterial color="#e0d6c5" roughness={0.92} />
      </mesh>
      {/* Rich Deep Teal-Slate Boucle Sofa */}
      <group position={[0, 0, -0.35]}>
        <RoundedBox args={[2.35, 0.36, 0.84]} radius={0.08} position={[0, 0.22, 0]}>
          <meshStandardMaterial color="#134e4a" roughness={0.85} />
        </RoundedBox>
        <RoundedBox args={[2.35, 0.48, 0.2]} radius={0.07} position={[0, 0.54, -0.32]}>
          <meshStandardMaterial color="#115e59" roughness={0.85} />
        </RoundedBox>
        {[-1.08, 1.08].map((ax, idx) => (
          <RoundedBox key={idx} args={[0.2, 0.34, 0.84]} radius={0.06} position={[ax, 0.42, 0]}>
            <meshStandardMaterial color="#115e59" roughness={0.85} />
          </RoundedBox>
        ))}
        {/* Amber & Warm Cream Accent Cushions */}
        <RoundedBox args={[0.36, 0.32, 0.12]} radius={0.04} position={[-0.75, 0.5, -0.14]} rotation={[0.15, 0.2, 0]}>
          <meshStandardMaterial color="#f59e0b" roughness={0.75} />
        </RoundedBox>
        <RoundedBox args={[0.36, 0.32, 0.12]} radius={0.04} position={[0.75, 0.5, -0.14]} rotation={[0.15, -0.2, 0]}>
          <meshStandardMaterial color="#fef3c7" roughness={0.75} />
        </RoundedBox>
      </group>

      {/* Matte Dark Charcoal Coffee Table + Warm Bronze Pedestal */}
      <mesh position={[0, 0.33, 0.85]}>
        <cylinderGeometry args={[0.64, 0.64, 0.05, 24]} />
        <meshStandardMaterial color="#1e293b" roughness={0.28} />
      </mesh>
      <mesh position={[0, 0.16, 0.85]}>
        <cylinderGeometry args={[0.16, 0.22, 0.32, 16]} />
        <meshStandardMaterial color="#b45309" metalness={0.45} roughness={0.35} />
      </mesh>

      {/* Terracotta Pouf */}
      <mesh position={[-1.5, 0.2, 0.85]} scale={[1.1, 0.68, 1.1]}>
        <sphereGeometry args={[0.36, 16, 12]} />
        <meshStandardMaterial color="#ea580c" roughness={0.82} />
      </mesh>

      {/* Matte Slate 75" Smart TV Console */}
      <group position={[0, 0, 2.35]}>
        <RoundedBox args={[2.1, 0.32, 0.36]} radius={0.03} position={[0, 0.16, 0]}>
          <meshStandardMaterial color="#334155" roughness={0.38} />
        </RoundedBox>
        <RoundedBox args={[1.95, 1.05, 0.06]} radius={0.025} position={[0, 0.88, 0]}>
          <meshStandardMaterial color="#0f172a" roughness={0.25} />
        </RoundedBox>
        <mesh position={[0, 0.88, -0.035]} rotation={[0, Math.PI, 0]}>
          <planeGeometry args={[1.84, 0.94]} />
          <meshBasicMaterial color="#1e3a8a" />
        </mesh>
      </group>
    </group>
  );
}

function PingPongTable({ position }: { position: [number, number, number] }) {
  return (
    <group position={position}>
      <RoundedBox args={[2.0, 0.055, 1.2]} radius={0.02} position={[0, 0.76, 0]}>
        <meshStandardMaterial color="#1e3a8a" roughness={0.35} />
      </RoundedBox>
      <mesh position={[0, 0.79, 0]}>
        <boxGeometry args={[1.96, 0.004, 0.02]} />
        <meshStandardMaterial color="#ffffff" />
      </mesh>
      <mesh position={[0, 0.87, 0]}>
        <boxGeometry args={[0.02, 0.14, 1.24]} />
        <meshStandardMaterial color="#e2e8f0" transparent opacity={0.78} />
      </mesh>
      {[
        [-0.72, -0.45],
        [0.72, -0.45],
        [-0.72, 0.45],
        [0.72, 0.45],
      ].map(([lx, lz], i) => (
        <mesh key={i} position={[lx, 0.38, lz]}>
          <cylinderGeometry args={[0.025, 0.025, 0.76, 8]} />
          <meshStandardMaterial color="#1e293b" metalness={0.5} />
        </mesh>
      ))}
    </group>
  );
}

function ArcadeCabinet({
  position,
  accentColor,
}: {
  position: [number, number, number];
  accentColor: string;
}) {
  return (
    <group position={position}>
      <RoundedBox args={[0.68, 1.75, 0.62]} radius={0.04} position={[0, 0.875, 0]}>
        <meshStandardMaterial color="#1e293b" roughness={0.42} />
      </RoundedBox>
      <mesh position={[0, 1.22, 0.29]} rotation={[-0.2, 0, 0]}>
        <planeGeometry args={[0.52, 0.4]} />
        <meshBasicMaterial color="#38bdf8" />
      </mesh>
      <mesh position={[0, 1.62, 0.31]}>
        <boxGeometry args={[0.56, 0.14, 0.03]} />
        <meshBasicMaterial color={accentColor} />
      </mesh>
      <mesh position={[0, 0.92, 0.36]}>
        <boxGeometry args={[0.64, 0.07, 0.2]} />
        <meshStandardMaterial color="#334155" />
      </mesh>
    </group>
  );
}

export function OfficeRoom({
  agents,
  bugs,
  onSelectAgent,
  onOpenBugBoard,
}: OfficeRoomProps) {
  return (
    <group>
      {/* Warm Greige Outer Stone Platform */}
      <mesh position={[0, -0.18, 0]}>
        <boxGeometry args={[28, 0.22, 21]} />
        <meshStandardMaterial color="#dfd7c8" roughness={0.88} />
      </mesh>

      {/* Main Warm Cream Studio Floor (20m x 12.5m) */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0, 0.05]}>
        <planeGeometry args={[20, 12.5]} />
        <meshStandardMaterial color="#f3ece0" roughness={0.78} />
      </mesh>

      {/* Central Hallway Floor + Champagne-Taupe Trim */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.008, 0.45]}>
        <planeGeometry args={[19.8, 1.6]} />
        <meshStandardMaterial color="#e8dfd0" roughness={0.72} />
      </mesh>
      {[-0.35, 1.25].map((tz, i) => (
        <mesh key={i} position={[0, 0.012, tz]}>
          <boxGeometry args={[19.8, 0.008, 0.04]} />
          <meshStandardMaterial color="#c4b59d" roughness={0.45} />
        </mesh>
      ))}

      {/* Subtle Room Zone Floors & Contrast Rugs */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[-6.15, 0.005, -3.22]}>
        <planeGeometry args={[7.3, 5.5]} />
        <meshStandardMaterial color="#f5eee2" roughness={0.75} />
      </mesh>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[-6.0, 0.01, -3.45]}>
        <planeGeometry args={[4.4, 3.0]} />
        <meshStandardMaterial color="#d5dde6" roughness={0.88} />
      </mesh>

      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[3.75, 0.005, -3.22]}>
        <planeGeometry args={[12.1, 5.5]} />
        <meshStandardMaterial color="#f5efe4" roughness={0.75} />
      </mesh>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[3.4, 0.01, -3.6]}>
        <planeGeometry args={[9.4, 2.7]} />
        <meshStandardMaterial color="#d9e2dc" roughness={0.88} />
      </mesh>

      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.005, 3.7]}>
        <planeGeometry args={[19.6, 4.7]} />
        <meshStandardMaterial color="#f6eedf" roughness={0.8} />
      </mesh>

      {/* Plain Warm Cream North Back Wall + Soft Contrast Panel Behind Leader */}
      <mesh position={[0, 1.5, -6.1]}>
        <boxGeometry args={[20.1, 3.0, 0.18]} />
        <meshStandardMaterial color="#efe7d8" roughness={0.65} />
      </mesh>
      <mesh position={[-6.0, 1.5, -5.99]}>
        <boxGeometry args={[6.8, 2.6, 0.03]} />
        <meshStandardMaterial color="#e4d9c7" roughness={0.62} />
      </mesh>
      {/* Subtle Top Warm Cove Light */}
      <mesh position={[-6.0, 2.84, -5.97]}>
        <boxGeometry args={[6.4, 0.04, 0.03]} />
        <meshBasicMaterial color="#fef08a" />
      </mesh>

      {/* Outer Plain Matte-Cream Side Walls (Low Cutaway Parapet with Matte Charcoal Cap in South Lounge) */}
      {[-9.95, 9.95].map((wx, idx) => (
        <group key={idx}>
          <mesh position={[wx, 1.3, -3.22]}>
            <boxGeometry args={[0.18, 2.6, 5.75]} />
            <meshStandardMaterial color="#ece3d3" roughness={0.65} />
          </mesh>
          <mesh position={[wx, 0.475, 3.15]}>
            <boxGeometry args={[0.16, 0.95, 6.2]} />
            <meshStandardMaterial color="#ece3d3" roughness={0.65} />
          </mesh>
          <mesh position={[wx, 0.97, 3.15]}>
            <boxGeometry args={[0.18, 0.04, 6.24]} />
            <meshStandardMaterial color="#475569" metalness={0.4} roughness={0.35} />
          </mesh>
        </group>
      ))}

      {/* Frameless Glass Partitions (ZERO Wood) */}
      <GlassPartition position={[-2.4, 0, -3.22]} size={[0.08, 2.35, 5.65]} />

      {/* North Corridor Glass Partition at z = -0.35 */}
      <GlassPartition position={[-8.45, 0, -0.35]} size={[2.9, 2.35, 0.08]} />
      <GlassPartition position={[-1.25, 0, -0.35]} size={[7.5, 2.35, 0.08]} />
      <GlassPartition position={[7.3, 0, -0.35]} size={[5.2, 2.35, 0.08]} />

      {/* South Lounge Low Glass Divider at z = 1.25 */}
      <GlassPartition position={[-5.65, 0, 1.25]} size={[8.5, 1.45, 0.08]} />
      <GlassPartition position={[5.65, 0, 1.25]} size={[8.5, 1.45, 0.08]} />

      {/* Room Doorways */}
      <RoomDoorway
        position={[ROOM_DOORS.leader_room[0], 0, -0.35]}
        doorWidth={2.0}
        roomCode="P.01"
        title="PHÒNG LEADER"
        accentColor="#2563eb"
      />
      <RoomDoorway
        position={[ROOM_DOORS.staff_room[0], 0, -0.35]}
        doorWidth={2.2}
        roomCode="P.02"
        title="PHÒNG NHÂN VIÊN"
        accentColor="#10b981"
      />
      <RoomDoorway
        position={[ROOM_DOORS.lounge_room[0], 0, 1.25]}
        doorWidth={2.8}
        roomCode="P.03"
        title="PHÒNG GIẢI TRÍ"
        accentColor="#d97706"
      />

      {/* P.01 Phòng Leader Furnishings (High-Contrast Slate + Terracotta Chairs) */}
      <group position={[-3.7, 0, -2.5]}>
        <mesh position={[0, 0.36, 0]}>
          <cylinderGeometry args={[0.06, 0.22, 0.72, 14]} />
          <meshStandardMaterial color="#1e293b" metalness={0.5} />
        </mesh>
        <mesh position={[0, 0.74, 0]}>
          <cylinderGeometry args={[0.64, 0.64, 0.04, 24]} />
          <meshStandardMaterial color="#334155" roughness={0.32} />
        </mesh>
        <LoungeChair position={[-0.82, 0, 0]} rotationY={Math.PI / 2} fabricColor="#c2410c" />
        <LoungeChair position={[0.82, 0, 0]} rotationY={-Math.PI / 2} fabricColor="#c2410c" />
      </group>
      <RoundedBox args={[0.44, 0.8, 2.1]} radius={0.03} position={[-9.5, 0.4, -3.6]}>
        <meshStandardMaterial color="#334155" roughness={0.45} />
      </RoundedBox>
      <OfficePlant position={[-9.1, 0, -5.35]} scale={1.1} />
      <OfficePlant position={[-3.2, 0, -5.35]} scale={0.95} />

      {/* P.02 Phòng Nhân viên Furnishings */}
      <FigmaMoodboard position={[1.5, 1.85, -5.98]} />
      <RoundedBox args={[1.45, 0.85, 0.42]} radius={0.03} position={[-1.7, 0.425, -5.6]}>
        <meshStandardMaterial color="#334155" roughness={0.45} />
      </RoundedBox>
      <CompactServerRack position={[9.0, 0, -5.2]} />
      <BugBoard3D bugs={bugs} onClick={onOpenBugBoard} />
      <OfficePlant position={[-1.5, 0, -1.2]} scale={1.0} />
      <OfficePlant position={[9.1, 0, -1.1]} scale={1.0} />

      {/* P.03 Phòng Giải trí Furnishings (Zero desks — Rich Color Contrast!) */}
      <EspressoBar position={[-5.6, 0, 2.05]} />
      {[
        { pos: [-7.2, 0, 4.35] as [number, number, number], chairColor: "#0f766e" },
        { pos: [-3.4, 0, 4.35] as [number, number, number], chairColor: "#b45309" },
      ].map(({ pos, chairColor }, bidx) => (
        <group key={bidx} position={pos}>
          <mesh position={[0, 0.37, 0]}>
            <cylinderGeometry args={[0.04, 0.18, 0.74, 12]} />
            <meshStandardMaterial color="#1e293b" metalness={0.5} />
          </mesh>
          <mesh position={[0, 0.75, 0]}>
            <cylinderGeometry args={[0.46, 0.46, 0.04, 22]} />
            <meshStandardMaterial color="#334155" roughness={0.32} />
          </mesh>
          <LoungeChair position={[-0.6, 0, 0.12]} rotationY={1.1} fabricColor={chairColor} />
          <LoungeChair position={[0.6, 0, 0.12]} rotationY={-1.1} fabricColor={chairColor} />
        </group>
      ))}

      <SofaTvLounge position={[0.8, 0, 2.8]} />
      <PingPongTable position={[6.4, 0, 3.85]} />
      <ArcadeCabinet position={[5.2, 0, 1.95]} accentColor="#ec4899" />
      <ArcadeCabinet position={[6.4, 0, 1.95]} accentColor="#06b6d4" />
      <OfficePlant position={[-9.2, 0, 5.4]} scale={1.05} />
      <OfficePlant position={[8.9, 0, 5.4]} scale={1.05} />
      <OfficePlant position={[3.6, 0, 5.4]} scale={0.95} />

      {/* 4 Core Workstations: 1 Leader in P.01 + 3 Staff in P.02 */}
      {CORE_ROLES.map((role) => (
        <Workstation
          key={role}
          spec={DESK_LAYOUT[role]}
          agent={agents[role]}
          onSelect={() => onSelectAgent(role, DESK_LAYOUT[role].standPos)}
        />
      ))}
    </group>
  );
}
