import { Html } from "@react-three/drei";
import { useFrame } from "@react-three/fiber";
import { useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";
import type { AvatarModelStyle } from "../../store/officeStore";
import type { AgentRole, AgentState } from "../../types";
import { ChibiCharacter3D, type ChibiPoseMode } from "./ChibiCharacter3D";
import { ModernHumanCharacter3D, type HumanPoseMode } from "./ModernHumanCharacter3D";
import { VrmAvatar, type VrmPoseMode } from "./VrmAvatar";
import {
  computeRoomToRoomWaypoints,
  DESK_LAYOUT,
  getDestinationForLocation,
  getStatusColor,
  getTargetRoom,
  IDLE_WORK_BUBBLES,
  LOUNGE_SPOTS,
  type RoomKey,
} from "./officeLayout";

interface AgentCharacterProps {
  agent: AgentState;
  isSelected: boolean;
  isBreakTime: boolean;
  avatarModelStyle: AvatarModelStyle;
  onSelect: (pos: [number, number, number]) => void;
}

type PoseMode =
  | "walk"
  | "work"
  | "sit"
  | "coffee"
  | "pingpong"
  | "alert"
  | "done"
  | "stand";

const VRM_ROLE_PATHS: Partial<Record<AgentRole, string>> = {
  asset: "/models/linh.vrm",
  dev: "/models/vy.vrm",
  ui_dev_2: "/models/vy.vrm",
};

export function AgentCharacter({
  agent,
  isSelected,
  isBreakTime,
  avatarModelStyle,
  onSelect,
}: AgentCharacterProps) {
  const rootRef = useRef<THREE.Group>(null);
  const haloRingRef = useRef<THREE.Mesh>(null);
  const movingRef = useRef<boolean>(false);
  const [isMovingState, setIsMovingState] = useState(false);

  const spec = DESK_LAYOUT[agent.role];
  const initialPos = useMemo(
    () => getDestinationForLocation(agent.role, agent.location, isBreakTime),
    // Initial spawn position only
    // eslint-disable-next-line react-hooks/exhaustive-deps
    []
  );
  const currentRoomRef = useRef<RoomKey>(
    getTargetRoom(agent.role, agent.location, isBreakTime)
  );
  const hasMountedRef = useRef(false);

  const waypointsRef = useRef<THREE.Vector3[]>([]);
  const wpIndexRef = useRef<number>(0);

  useEffect(() => {
    if (!hasMountedRef.current) {
      hasMountedRef.current = true;
      return;
    }
    const targetRoom = getTargetRoom(agent.role, agent.location, isBreakTime);
    const dest = getDestinationForLocation(agent.role, agent.location, isBreakTime);
    const wps = computeRoomToRoomWaypoints(currentRoomRef.current, targetRoom, dest);
    waypointsRef.current = wps.map((p) => new THREE.Vector3(...p));
    wpIndexRef.current = 0;
    currentRoomRef.current = targetRoom;
  }, [agent.role, agent.location, isBreakTime]);

  const isInLounge = isBreakTime || agent.location === "lounge";

  useFrame((state, delta) => {
    const group = rootRef.current;
    if (!group) return;

    const wps = waypointsRef.current;
    let moving = false;

    if (wpIndexRef.current < wps.length) {
      const target = wps[wpIndexRef.current];
      const dist = group.position.distanceTo(target);
      if (dist > 0.08) {
        moving = true;
        const speed = 3.2 * Math.min(delta, 0.05);
        const dir = target.clone().sub(group.position).normalize();
        group.position.addScaledVector(dir, Math.min(speed, dist));
        const targetYaw = Math.atan2(dir.x, dir.z);
        group.rotation.y = THREE.MathUtils.lerp(group.rotation.y, targetYaw, 0.22);
      } else {
        group.position.copy(target);
        wpIndexRef.current += 1;
      }
    } else if (isInLounge) {
      group.rotation.y = THREE.MathUtils.lerp(
        group.rotation.y,
        LOUNGE_SPOTS[agent.role].rotY,
        0.14
      );
    } else if (agent.location === "leader_desk" && agent.role !== "leader") {
      group.rotation.y = THREE.MathUtils.lerp(group.rotation.y, Math.PI, 0.14);
    } else if (agent.location === "desk" || agent.role === "leader") {
      group.rotation.y = THREE.MathUtils.lerp(
        group.rotation.y,
        spec.deskRotationY,
        0.14
      );
    } else if (agent.location === "bug_board") {
      group.rotation.y = THREE.MathUtils.lerp(group.rotation.y, Math.PI / 2, 0.14);
    }

    if (movingRef.current !== moving) {
      movingRef.current = moving;
      setIsMovingState(moving);
    }
    if (haloRingRef.current) {
      haloRingRef.current.rotation.z = state.clock.elapsedTime * 1.4;
    }
  });

  const isCalmDeskIdle = !isInLounge && agent.status === "idle";
  const statusColor = isInLounge
    ? agent.status === "done"
      ? "#0d9488"
      : "#f59e0b"
    : isCalmDeskIdle
      ? "#3b82f6"
      : getStatusColor(agent.status);

  const bubbleText = isBreakTime
    ? LOUNGE_SPOTS[agent.role].activity
    : agent.location === "lounge"
      ? agent.bubble_text || LOUNGE_SPOTS[agent.role].activity
      : isCalmDeskIdle
        ? IDLE_WORK_BUBBLES[agent.role][0]
        : agent.bubble_text;

  let poseMode: PoseMode = "stand";
  if (isMovingState) {
    poseMode = "walk";
  } else if (isInLounge) {
    poseMode =
      agent.role === "qa"
        ? "pingpong"
        : agent.role === "asset"
          ? "sit"
          : "coffee";
  } else if (isCalmDeskIdle) {
    poseMode = "work";
  } else if (agent.status === "working_ai" || agent.status === "working_offline") {
    poseMode = agent.location === "desk" || agent.role === "leader" ? "work" : "stand";
  } else if (agent.status === "waiting_review" || agent.status === "blocked") {
    poseMode = agent.role === "leader" && agent.location === "leader_desk" ? "sit" : "alert";
  } else if (agent.status === "done") {
    poseMode = agent.location === "desk" || agent.role === "leader" ? "work" : "done";
  }

  const vrmPath = VRM_ROLE_PATHS[agent.role];

  return (
    <group
      ref={rootRef}
      position={initialPos}
      onClick={(e) => {
        e.stopPropagation();
        const pos = rootRef.current?.position;
        onSelect(pos ? [pos.x, pos.y, pos.z] : initialPos);
      }}
    >
      {/* Floor Halo Ring */}
      <mesh
        ref={haloRingRef}
        rotation={[-Math.PI / 2, 0, 0]}
        position={[0, 0.025, 0]}
      >
        <ringGeometry args={[0.38, isSelected ? 0.56 : 0.46, 32]} />
        <meshBasicMaterial color={isSelected ? "#ffffff" : statusColor} />
      </mesh>

      {/* Real Human (VRoid VRM + Procedural Human) or Chibi Pixar 3D */}
      {avatarModelStyle === "rpm" && vrmPath ? (
        <VrmAvatar
          modelPath={vrmPath}
          role={agent.role}
          poseMode={poseMode as VrmPoseMode}
          isMoving={isMovingState}
        />
      ) : avatarModelStyle === "rpm" ? (
        <ModernHumanCharacter3D
          role={agent.role}
          poseMode={poseMode as HumanPoseMode}
          isMoving={isMovingState}
        />
      ) : (
        <ChibiCharacter3D
          role={agent.role}
          poseMode={poseMode as ChibiPoseMode}
          isMoving={isMovingState}
        />
      )}

      {/* Floating Status Nameplate & Live Activity Bubble */}
      <Html
        position={[0, avatarModelStyle === "chibi" ? 1.72 : 1.98, 0]}
        center
        distanceFactor={13}
        zIndexRange={[10, 0]}
      >
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: 4,
            pointerEvents: "none",
          }}
        >
          {bubbleText && (
            <div
              className="agent-bubble-3d"
              style={{ borderColor: statusColor }}
              title={bubbleText}
            >
              {bubbleText}
            </div>
          )}
          <div
            className="agent-name-3d"
            style={{
              borderColor: isSelected ? "#ffffff" : statusColor,
            }}
          >
            {agent.name}
          </div>
        </div>
      </Html>
    </group>
  );
}
