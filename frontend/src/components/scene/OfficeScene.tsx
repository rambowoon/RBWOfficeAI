import { OrbitControls } from "@react-three/drei";
import { Canvas, useFrame } from "@react-three/fiber";
import { Coffee } from "lucide-react";
import { useRef, useState } from "react";
import type { ComponentRef } from "react";
import * as THREE from "three";
import { useOfficeStore, type AvatarModelStyle } from "../../store/officeStore";
import { normalizeOfficeAgents } from "../../utils/defaultAgents";
import { AgentCharacter } from "./AgentCharacter";
import { BUG_BOARD_POS, CAMERA_ZONES } from "./officeLayout";
import { OfficeRoom } from "./OfficeRoom";

const MODEL_STYLE_OPTIONS: Array<{ id: AvatarModelStyle; label: string }> = [
  { id: "rpm", label: "🧑 Người thật (VRM / 3D)" },
  { id: "chibi", label: "✨ Chibi Pixar 3D" },
];

function CameraRig({
  cameraGoal,
  onClearGoal,
}: {
  cameraGoal: [number, number, number] | null;
  onClearGoal: () => void;
}) {
  const controlsRef = useRef<ComponentRef<typeof OrbitControls>>(null);
  const focusTarget = useOfficeStore((s) => s.focusTarget);
  const setFocusTarget = useOfficeStore((s) => s.setFocusTarget);
  const targetVec = useRef(new THREE.Vector3(0, 0.4, 0));
  const posVec = useRef(new THREE.Vector3(0, 12.2, 14.2));

  useFrame((state) => {
    const ctrl = controlsRef.current;
    if (!ctrl) return;
    if (focusTarget) {
      targetVec.current.set(focusTarget[0], 0.8, focusTarget[2]);
      ctrl.target.lerp(targetVec.current, 0.08);
      ctrl.update();
    }
    if (cameraGoal) {
      posVec.current.set(cameraGoal[0], cameraGoal[1], cameraGoal[2]);
      if (state.camera.position.distanceTo(posVec.current) > 0.3) {
        state.camera.position.lerp(posVec.current, 0.07);
      } else {
        onClearGoal();
      }
    }
  });

  return (
    <OrbitControls
      ref={controlsRef}
      makeDefault
      enableDamping
      dampingFactor={0.08}
      maxPolarAngle={Math.PI / 2.15}
      minDistance={5}
      maxDistance={28}
      onStart={() => {
        onClearGoal();
        setFocusTarget(null);
      }}
    />
  );
}

export function OfficeScene() {
  const projects = useOfficeStore((s) => s.projects);
  const activeProjectId = useOfficeStore((s) => s.activeProjectId);
  const selectedAgentId = useOfficeStore((s) => s.selectedAgentId);
  const isBreakTime = useOfficeStore((s) => s.isBreakTime);
  const avatarModelStyle = useOfficeStore((s) => s.avatarModelStyle);
  const toggleBreakTime = useOfficeStore((s) => s.toggleBreakTime);
  const setAvatarModelStyle = useOfficeStore((s) => s.setAvatarModelStyle);
  const selectAgent = useOfficeStore((s) => s.selectAgent);
  const setShowBugBoard = useOfficeStore((s) => s.setShowBugBoard);
  const setFocusTarget = useOfficeStore((s) => s.setFocusTarget);

  const [activeZone, setActiveZone] = useState("overview");
  const [cameraGoal, setCameraGoal] = useState<[number, number, number] | null>(null);

  const activeProject = projects.find((p) => p.id === activeProjectId) ?? null;
  const agents = normalizeOfficeAgents(activeProject?.agents);
  const bugs = activeProject?.bugs ?? [];

  return (
    <div style={{ width: "100%", height: "100%", position: "relative" }}>
      {/* Department Camera Switcher, Break-Time & 3D GLB Avatar Model Bar */}
      <div
        className="glass-panel"
        style={{
          position: "absolute",
          top: 72,
          left: 12,
          zIndex: 19,
          borderRadius: 12,
          padding: "6px 10px",
          display: "flex",
          alignItems: "center",
          gap: 6,
          flexWrap: "wrap",
          maxWidth: "calc(100vw - 24px)",
        }}
      >
        {CAMERA_ZONES.map((zone) => {
          const isActive = activeZone === zone.id;
          return (
            <button
              key={zone.id}
              type="button"
              onClick={() => {
                setActiveZone(zone.id);
                setFocusTarget(zone.target);
                setCameraGoal(zone.position);
              }}
              style={{
                background: isActive ? "#3b82f6" : "rgba(15,23,42,0.75)",
                color: isActive ? "#ffffff" : "#cbd5e1",
                border: "1px solid rgba(148,163,184,0.25)",
                borderRadius: 8,
                padding: "4px 10px",
                fontSize: 11,
                fontWeight: 600,
                cursor: "pointer",
              }}
            >
              {zone.label}
            </button>
          );
        })}

        <button
          type="button"
          onClick={() => {
            if (!isBreakTime) {
              setActiveZone("lounge_room");
              setCameraGoal([0, 7.2, 11.4]);
            }
            toggleBreakTime();
          }}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 5,
            background: isBreakTime ? "#f59e0b" : "rgba(245,158,11,0.16)",
            color: isBreakTime ? "#0f172a" : "#fcd34d",
            border: "1px solid rgba(245,158,11,0.5)",
            borderRadius: 8,
            padding: "4px 10px",
            fontSize: 11,
            fontWeight: 700,
            cursor: "pointer",
          }}
        >
          <Coffee size={13} />
          <span>{isBreakTime ? "💻 Về bàn làm việc" : "☕ Ra Canteen nghỉ ngơi"}</span>
        </button>

        <span
          style={{
            width: 1,
            height: 18,
            background: "rgba(148,163,184,0.25)",
            margin: "0 2px",
          }}
        />

        {MODEL_STYLE_OPTIONS.map((opt) => {
          const active = avatarModelStyle === opt.id;
          return (
            <button
              key={opt.id}
              type="button"
              onClick={() => setAvatarModelStyle(opt.id)}
              style={{
                background: active ? "#8b5cf6" : "rgba(15,23,42,0.75)",
                color: active ? "#ffffff" : "#cbd5e1",
                border: "1px solid rgba(139,92,246,0.35)",
                borderRadius: 8,
                padding: "4px 9px",
                fontSize: 11,
                fontWeight: 600,
                cursor: "pointer",
              }}
            >
              {opt.label}
            </button>
          );
        })}
      </div>

      <Canvas
        dpr={[1, 1.5]}
        gl={{ antialias: true, powerPreference: "default" }}
        camera={{ position: [0, 12.2, 14.2], fov: 42 }}
        onPointerMissed={() => {
          selectAgent(null, null);
          setCameraGoal(null);
        }}
      >
        <color attach="background" args={["#e9e3d8"]} />
        <fog attach="fog" args={["#e9e3d8", 30, 58]} />

        {/* Bright Warm Studio Daylight Lighting (Shadow-free for low-end PCs) */}
        <ambientLight intensity={1.55} color="#fffdf9" />
        <hemisphereLight args={["#fffdf7", "#e8dfd1", 1.15]} />
        <directionalLight position={[12, 22, 14]} intensity={1.9} color="#fffbeb" />
        <directionalLight position={[-14, 16, -10]} intensity={0.95} color="#f0f9ff" />

        {/* 3 Room Ceiling Lights */}
        <pointLight position={[-6.0, 3.2, -3.3]} intensity={1.3} distance={14} color="#fffaf0" />
        <pointLight position={[3.4, 3.2, -3.3]} intensity={1.3} distance={15} color="#fefce8" />
        <pointLight position={[0, 3.2, 3.6]} intensity={1.35} distance={16} color="#fff7ed" />

        <OfficeRoom
          agents={agents}
          bugs={bugs}
          onSelectAgent={(id, pos) => {
            setCameraGoal(null);
            selectAgent(id, pos);
          }}
          onOpenBugBoard={() => {
            setCameraGoal(null);
            setFocusTarget(BUG_BOARD_POS);
            setShowBugBoard(true);
          }}
        />

        {Object.values(agents).map((agent) => (
          <AgentCharacter
            key={agent.id}
            agent={agent}
            isSelected={selectedAgentId === agent.id}
            isBreakTime={isBreakTime}
            avatarModelStyle={avatarModelStyle}
            onSelect={(pos) => {
              setCameraGoal(null);
              selectAgent(agent.id, pos);
            }}
          />
        ))}

        <CameraRig
          cameraGoal={cameraGoal}
          onClearGoal={() => setCameraGoal(null)}
        />
      </Canvas>
    </div>
  );
}
