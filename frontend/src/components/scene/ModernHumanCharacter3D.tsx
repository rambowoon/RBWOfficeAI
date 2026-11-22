import { RoundedBox } from "@react-three/drei";
import { useFrame } from "@react-three/fiber";
import { useMemo, useRef } from "react";
import * as THREE from "three";
import type { AgentRole } from "../../types";

export type HumanPoseMode =
  | "walk"
  | "work"
  | "sit"
  | "coffee"
  | "pingpong"
  | "alert"
  | "done"
  | "stand";

interface ModernHumanCharacter3DProps {
  role: AgentRole;
  poseMode: HumanPoseMode;
  isMoving: boolean;
}

const ROLE_ORDER: Record<AgentRole, number> = {
  leader: 0,
  dev: 1,
  asset: 1,
  seeder: 2,
  config: 3,
  qa: 4,
  ui_dev_1: 5,
  ui_dev_2: 6,
};

interface HumanAppearance {
  skin: string;
  hair: string;
  shirt: string;
  shirtStyle: "tshirt" | "dress_shirt" | "open_oxford";
  innerTee?: string;
  tieColor?: string;
  bottomType: "slacks" | "chinos" | "skirt_a" | "skirt_pleated" | "skirt_pencil";
  bottomColor: string;
  shoeColor: string;
  soleColor: string;
  scale: number;
}

const APPEARANCES: Record<AgentRole, HumanAppearance> = {
  leader: {
    skin: "#f6cfa9",
    hair: "#18181b",
    shirt: "#ffffff",
    shirtStyle: "dress_shirt",
    tieColor: "#1e3a8a",
    bottomType: "slacks",
    bottomColor: "#0f172a",
    shoeColor: "#18181b",
    soleColor: "#18181b",
    scale: 1.03,
  },
  ui_dev_1: {
    skin: "#f4c8a2",
    hair: "#171717",
    shirt: "#2563eb",
    shirtStyle: "tshirt",
    bottomType: "chinos",
    bottomColor: "#1e293b",
    shoeColor: "#f8fafc",
    soleColor: "#e2e8f0",
    scale: 1.0,
  },
  seeder: {
    skin: "#f3c69f",
    hair: "#3b2214",
    shirt: "#10b981",
    shirtStyle: "tshirt",
    bottomType: "chinos",
    bottomColor: "#d6c7b2",
    shoeColor: "#ffffff",
    soleColor: "#cbd5e1",
    scale: 0.99,
  },
  config: {
    skin: "#f5cba7",
    hair: "#0f172a",
    shirt: "#38bdf8",
    shirtStyle: "open_oxford",
    innerTee: "#ffffff",
    bottomType: "slacks",
    bottomColor: "#334155",
    shoeColor: "#1e293b",
    soleColor: "#f8fafc",
    scale: 1.01,
  },
  dev: {
    skin: "#f8d5b4",
    hair: "#26150c",
    shirt: "#f43f5e",
    shirtStyle: "tshirt",
    bottomType: "skirt_pleated",
    bottomColor: "#1e293b",
    shoeColor: "#ffffff",
    soleColor: "#f43f5e",
    scale: 0.94,
  },
  asset: {
    skin: "#f8d5b4",
    hair: "#2e190e",
    shirt: "#fffbeb",
    shirtStyle: "dress_shirt",
    bottomType: "skirt_a",
    bottomColor: "#0d9488",
    shoeColor: "#fef3c7",
    soleColor: "#d97706",
    scale: 0.95,
  },
  ui_dev_2: {
    skin: "#f8d5b4",
    hair: "#26150c",
    shirt: "#f43f5e",
    shirtStyle: "tshirt",
    bottomType: "skirt_pleated",
    bottomColor: "#1e293b",
    shoeColor: "#ffffff",
    soleColor: "#f43f5e",
    scale: 0.94,
  },
  qa: {
    skin: "#f5cba7",
    hair: "#0f172a",
    shirt: "#38bdf8",
    shirtStyle: "open_oxford",
    innerTee: "#ffffff",
    bottomType: "slacks",
    bottomColor: "#334155",
    shoeColor: "#1e293b",
    soleColor: "#f8fafc",
    scale: 1.01,
  },
};

function AsianHairStyle({ role, color }: { role: AgentRole; color: string }) {
  if (role === "leader") {
    // Korean side-part comma hair
    return (
      <group>
        <mesh position={[0, 0.025, -0.01]} scale={[0.96, 1.04, 1.0]}>
          <sphereGeometry args={[0.12, 22, 16, 0, Math.PI * 2, 0, Math.PI * 0.56]} />
          <meshStandardMaterial color={color} roughness={0.65} />
        </mesh>
        <RoundedBox
          args={[0.11, 0.045, 0.09]}
          radius={0.02}
          position={[0.03, 0.09, 0.055]}
          rotation={[-0.25, 0, -0.18]}
        >
          <meshStandardMaterial color={color} roughness={0.65} />
        </RoundedBox>
        <RoundedBox
          args={[0.075, 0.04, 0.07]}
          radius={0.018}
          position={[-0.045, 0.078, 0.068]}
          rotation={[0.25, 0.2, 0.25]}
        >
          <meshStandardMaterial color={color} roughness={0.65} />
        </RoundedBox>
      </group>
    );
  }

  if (role === "ui_dev_1") {
    // Textured two-block short crop + over-neck headphones
    return (
      <group>
        <mesh position={[0, 0.02, -0.008]} scale={[0.98, 1.04, 1.02]}>
          <sphereGeometry args={[0.122, 20, 16, 0, Math.PI * 2, 0, Math.PI * 0.58]} />
          <meshStandardMaterial color={color} roughness={0.72} />
        </mesh>
        <RoundedBox
          args={[0.16, 0.045, 0.06]}
          radius={0.02}
          position={[0, 0.078, 0.08]}
          rotation={[0.22, 0, 0]}
        >
          <meshStandardMaterial color={color} roughness={0.72} />
        </RoundedBox>
      </group>
    );
  }

  if (role === "seeder") {
    // Layered chestnut curtain bangs
    return (
      <group>
        <mesh position={[0, 0.02, -0.01]} scale={[0.98, 1.04, 1.0]}>
          <sphereGeometry args={[0.122, 20, 16, 0, Math.PI * 2, 0, Math.PI * 0.58]} />
          <meshStandardMaterial color={color} roughness={0.68} />
        </mesh>
        {[-0.05, 0.05].map((bx, i) => (
          <RoundedBox
            key={i}
            args={[0.065, 0.055, 0.055]}
            radius={0.02}
            position={[bx, 0.07, 0.088]}
            rotation={[0.25, 0, i === 0 ? 0.22 : -0.22]}
          >
            <meshStandardMaterial color={color} roughness={0.68} />
          </RoundedBox>
        ))}
      </group>
    );
  }

  if (role === "config") {
    // Neat short fade + modern glasses
    return (
      <group>
        <mesh position={[0, 0.022, -0.012]} scale={[0.95, 1.02, 0.99]}>
          <sphereGeometry args={[0.119, 20, 16, 0, Math.PI * 2, 0, Math.PI * 0.52]} />
          <meshStandardMaterial color={color} roughness={0.7} />
        </mesh>
        <group position={[0, 0.008, 0.114]}>
          {[-0.036, 0.036].map((gx, i) => (
            <mesh key={i} position={[gx, 0, 0]}>
              <torusGeometry args={[0.024, 0.0035, 8, 18]} />
              <meshStandardMaterial color="#1e293b" metalness={0.6} />
            </mesh>
          ))}
          <mesh>
            <boxGeometry args={[0.022, 0.004, 0.004]} />
            <meshStandardMaterial color="#1e293b" />
          </mesh>
        </group>
      </group>
    );
  }

  if (role === "asset") {
    // Long flowing dark-brown hair past shoulders + pearl hair clip
    return (
      <group>
        <mesh position={[0, 0.02, -0.01]} scale={[0.98, 1.06, 1.02]}>
          <sphereGeometry args={[0.123, 22, 16, 0, Math.PI * 2, 0, Math.PI * 0.62]} />
          <meshStandardMaterial color={color} roughness={0.55} />
        </mesh>
        <RoundedBox
          args={[0.21, 0.26, 0.1]}
          radius={0.045}
          position={[0, -0.09, -0.075]}
        >
          <meshStandardMaterial color={color} roughness={0.55} />
        </RoundedBox>
        {[-0.1, 0.1].map((sx, i) => (
          <mesh key={i} position={[sx, -0.06, -0.01]}>
            <capsuleGeometry args={[0.036, 0.16, 6, 10]} />
            <meshStandardMaterial color={color} roughness={0.55} />
          </mesh>
        ))}
        <mesh position={[0.085, 0.075, 0.075]}>
          <boxGeometry args={[0.032, 0.012, 0.012]} />
          <meshStandardMaterial color="#fde68a" metalness={0.5} />
        </mesh>
      </group>
    );
  }

  if (role === "dev" || role === "ui_dev_2") {
    // High bouncy ponytail with side bangs
    return (
      <group>
        <mesh position={[0, 0.02, -0.01]} scale={[0.98, 1.05, 1.0]}>
          <sphereGeometry args={[0.122, 22, 16, 0, Math.PI * 2, 0, Math.PI * 0.6]} />
          <meshStandardMaterial color={color} roughness={0.55} />
        </mesh>
        <mesh position={[0, 0.09, -0.11]} rotation={[0.45, 0, 0]}>
          <sphereGeometry args={[0.03, 10, 10]} />
          <meshStandardMaterial color="#f43f5e" />
        </mesh>
        <mesh position={[0, -0.02, -0.145]} rotation={[0.28, 0, 0]}>
          <capsuleGeometry args={[0.046, 0.2, 8, 12]} />
          <meshStandardMaterial color={color} roughness={0.55} />
        </mesh>
      </group>
    );
  }

  // QA (Tuấn - Male): Neat short textured fade + modern dark glasses
  return (
    <group>
      <mesh position={[0, 0.024, -0.01]} scale={[0.96, 1.03, 1.0]}>
        <sphereGeometry args={[0.12, 20, 16, 0, Math.PI * 2, 0, Math.PI * 0.54]} />
        <meshStandardMaterial color={color} roughness={0.68} />
      </mesh>
      <RoundedBox
        args={[0.15, 0.04, 0.055]}
        radius={0.018}
        position={[0, 0.08, 0.075]}
        rotation={[0.22, 0, 0]}
      >
        <meshStandardMaterial color={color} roughness={0.68} />
      </RoundedBox>
      <group position={[0, 0.008, 0.114]}>
        {[-0.036, 0.036].map((gx, i) => (
          <mesh key={i} position={[gx, 0, 0]}>
            <torusGeometry args={[0.025, 0.0036, 8, 18]} />
            <meshStandardMaterial color="#0f172a" metalness={0.6} />
          </mesh>
        ))}
        <mesh>
          <boxGeometry args={[0.022, 0.004, 0.004]} />
          <meshStandardMaterial color="#0f172a" />
        </mesh>
      </group>
    </group>
  );
}

function HumanTorsoOutfit({
  role,
  spec,
}: {
  role: AgentRole;
  spec: HumanAppearance;
}) {
  const isFemale =
    spec.bottomType === "skirt_a" ||
    spec.bottomType === "skirt_pleated" ||
    spec.bottomType === "skirt_pencil";

  const torsoW = isFemale ? 0.27 : 0.32;
  const torsoD = isFemale ? 0.165 : 0.185;

  return (
    <group>
      {/* Main Shirt Body */}
      <RoundedBox
        args={[torsoW, 0.44, torsoD]}
        radius={0.055}
        position={[0, 0.24, 0]}
      >
        <meshStandardMaterial color={spec.shirt} roughness={0.68} />
      </RoundedBox>

      {/* Crew-neck rib collar for T-shirt */}
      {spec.shirtStyle === "tshirt" && (
        <mesh position={[0, 0.45, 0.01]} rotation={[Math.PI / 2, 0, 0]}>
          <torusGeometry args={[0.072, 0.014, 8, 18]} />
          <meshStandardMaterial color={role === "ui_dev_1" ? "#ffffff" : "#065f46"} roughness={0.7} />
        </mesh>
      )}

      {/* Collared Button-Down Dress Shirt details */}
      {spec.shirtStyle === "dress_shirt" && (
        <group>
          {/* Folded Shirt Collar */}
          {[-0.036, 0.036].map((cx, i) => (
            <RoundedBox
              key={i}
              args={[0.055, 0.045, 0.035]}
              radius={0.008}
              position={[cx, 0.455, 0.05]}
              rotation={[0.3, 0, i === 0 ? 0.35 : -0.35]}
            >
              <meshStandardMaterial color={role === "qa" ? "#ffffff" : spec.shirt} roughness={0.55} />
            </RoundedBox>
          ))}
          {/* Center Placket & Buttons */}
          <mesh position={[0, 0.24, torsoD / 2 + 0.004]}>
            <boxGeometry args={[0.022, 0.36, 0.006]} />
            <meshStandardMaterial color="#e2e8f0" roughness={0.6} />
          </mesh>
          {spec.tieColor && (
            <RoundedBox
              args={[0.032, 0.25, 0.014]}
              radius={0.005}
              position={[0, 0.29, torsoD / 2 + 0.01]}
            >
              <meshStandardMaterial color={spec.tieColor} roughness={0.5} />
            </RoundedBox>
          )}
        </group>
      )}

      {/* Open Oxford Shirt over White Inner Tee */}
      {spec.shirtStyle === "open_oxford" && (
        <group>
          <RoundedBox
            args={[0.11, 0.41, torsoD + 0.008]}
            radius={0.025}
            position={[0, 0.25, 0.004]}
          >
            <meshStandardMaterial color={spec.innerTee || "#ffffff"} roughness={0.7} />
          </RoundedBox>
          {[-0.04, 0.04].map((cx, i) => (
            <RoundedBox
              key={i}
              args={[0.05, 0.045, 0.03]}
              radius={0.008}
              position={[cx, 0.455, 0.048]}
              rotation={[0.3, 0, i === 0 ? 0.35 : -0.35]}
            >
              <meshStandardMaterial color={spec.shirt} roughness={0.6} />
            </RoundedBox>
          ))}
        </group>
      )}

      {/* Waistband / Belt */}
      <RoundedBox
        args={[torsoW + 0.01, 0.04, torsoD + 0.01]}
        radius={0.01}
        position={[0, 0.03, 0]}
      >
        <meshStandardMaterial color="#1e293b" roughness={0.5} />
      </RoundedBox>

      {/* Headphones worn around neck for Tuấn */}
      {role === "ui_dev_1" && (
        <group position={[0, 0.44, 0.03]}>
          <mesh rotation={[Math.PI / 2 - 0.3, 0, 0]}>
            <torusGeometry args={[0.095, 0.013, 8, 20, Math.PI * 1.25]} />
            <meshStandardMaterial color="#0f172a" roughness={0.4} />
          </mesh>
        </group>
      )}
    </group>
  );
}

export function ModernHumanCharacter3D({
  role,
  poseMode,
  isMoving,
}: ModernHumanCharacter3DProps) {
  const hipsRef = useRef<THREE.Group>(null);
  const torsoRef = useRef<THREE.Group>(null);
  const headRef = useRef<THREE.Group>(null);
  const skirtRef = useRef<THREE.Group>(null);
  const leftArmRef = useRef<THREE.Group>(null);
  const rightArmRef = useRef<THREE.Group>(null);
  const leftForeArmRef = useRef<THREE.Group>(null);
  const rightForeArmRef = useRef<THREE.Group>(null);
  const leftThighRef = useRef<THREE.Group>(null);
  const rightThighRef = useRef<THREE.Group>(null);
  const leftCalfRef = useRef<THREE.Group>(null);
  const rightCalfRef = useRef<THREE.Group>(null);

  const spec = useMemo(() => APPEARANCES[role], [role]);
  const timeOffset = ROLE_ORDER[role] * 1.37;

  const isSkirt =
    spec.bottomType === "skirt_a" ||
    spec.bottomType === "skirt_pleated" ||
    spec.bottomType === "skirt_pencil";

  const isShortSleeve = spec.shirtStyle === "tshirt";
  const forearmColor = spec.skin; // Bare warm Asian forearms (short-sleeve tee or rolled-up shirt cuffs)

  useFrame((state) => {
    const t = state.clock.elapsedTime + timeOffset;
    const isSeated = !isMoving && (poseMode === "work" || poseMode === "sit");

    if (hipsRef.current) {
      const targetHipY = isSeated
        ? 0.52
        : isMoving || poseMode === "walk"
        ? 0.88 + Math.abs(Math.sin(t * 9.5)) * 0.03
        : 0.88 + Math.sin(t * 2.0) * 0.008;
      hipsRef.current.position.y = THREE.MathUtils.lerp(
        hipsRef.current.position.y,
        targetHipY,
        0.22
      );
    }

    if (skirtRef.current) {
      skirtRef.current.rotation.x = THREE.MathUtils.lerp(
        skirtRef.current.rotation.x,
        isSeated ? -1.16 : 0,
        0.22
      );
      skirtRef.current.position.set(0, isSeated ? -0.01 : -0.14, isSeated ? 0.14 : 0.01);
    }

    if (isMoving || poseMode === "walk") {
      const stride = Math.sin(t * 9.5);
      const kneeL = Math.max(0, -Math.cos(t * 9.5)) * 0.55;
      const kneeR = Math.max(0, Math.cos(t * 9.5)) * 0.55;
      if (leftThighRef.current) leftThighRef.current.rotation.x = stride * 0.5;
      if (rightThighRef.current) rightThighRef.current.rotation.x = -stride * 0.5;
      if (leftCalfRef.current) leftCalfRef.current.rotation.x = kneeL;
      if (rightCalfRef.current) rightCalfRef.current.rotation.x = kneeR;

      if (leftArmRef.current) {
        leftArmRef.current.rotation.set(-stride * 0.45, 0, 0.12);
      }
      if (rightArmRef.current) {
        rightArmRef.current.rotation.set(stride * 0.45, 0, -0.12);
      }
      if (leftForeArmRef.current) leftForeArmRef.current.rotation.x = -0.25;
      if (rightForeArmRef.current) rightForeArmRef.current.rotation.x = -0.25;
      if (torsoRef.current) torsoRef.current.rotation.set(0.04, stride * 0.06, 0);
      if (headRef.current) headRef.current.rotation.set(0, 0, 0);
    } else if (poseMode === "work") {
      // Natural seated keyboard typing + mouse movement above desk top
      const typeL = Math.sin(t * 14) * 0.14;
      const typeR = Math.cos(t * 14) * 0.14;
      const mouseMove = Math.sin(t * 2.1) * 0.05;

      if (leftThighRef.current) leftThighRef.current.rotation.x = -1.48;
      if (rightThighRef.current) rightThighRef.current.rotation.x = -1.48;
      if (leftCalfRef.current) leftCalfRef.current.rotation.x = 1.48;
      if (rightCalfRef.current) rightCalfRef.current.rotation.x = 1.48;

      if (leftArmRef.current) {
        leftArmRef.current.rotation.set(-1.04, -0.06, 0.06);
      }
      if (rightArmRef.current) {
        rightArmRef.current.rotation.set(-1.04, 0.06 + mouseMove, -0.06);
      }
      if (leftForeArmRef.current) leftForeArmRef.current.rotation.x = -0.68 + typeL;
      if (rightForeArmRef.current) rightForeArmRef.current.rotation.x = -0.68 + typeR;
      if (torsoRef.current) {
        torsoRef.current.rotation.set(0.1, Math.sin(t * 0.8) * 0.03, 0);
      }
      if (headRef.current) {
        headRef.current.rotation.set(0.08, Math.sin(t * 1.1) * 0.18, 0);
      }
    } else if (poseMode === "sit") {
      if (leftThighRef.current) leftThighRef.current.rotation.x = -1.36;
      if (rightThighRef.current) rightThighRef.current.rotation.x = -1.36;
      if (leftCalfRef.current) leftCalfRef.current.rotation.x = 1.32;
      if (rightCalfRef.current) rightCalfRef.current.rotation.x = 1.32;
      if (leftArmRef.current) leftArmRef.current.rotation.set(-0.22, 0, 0.12);
      if (rightArmRef.current) rightArmRef.current.rotation.set(-0.22, 0, -0.12);
      if (leftForeArmRef.current) leftForeArmRef.current.rotation.x = -0.45;
      if (rightForeArmRef.current) rightForeArmRef.current.rotation.x = -0.45;
      if (torsoRef.current) torsoRef.current.rotation.set(-0.05, 0, 0);
      if (headRef.current) headRef.current.rotation.set(0, Math.sin(t * 1.0) * 0.18, 0);
    } else if (poseMode === "alert") {
      if (leftThighRef.current) leftThighRef.current.rotation.x = 0;
      if (rightThighRef.current) rightThighRef.current.rotation.x = 0;
      if (leftCalfRef.current) leftCalfRef.current.rotation.x = 0;
      if (rightCalfRef.current) rightCalfRef.current.rotation.x = 0;
      if (leftArmRef.current) leftArmRef.current.rotation.set(0, 0, 0.12);
      if (rightArmRef.current) {
        rightArmRef.current.rotation.set(-0.3, 0, -2.1 + Math.sin(t * 6.5) * 0.22);
      }
      if (leftForeArmRef.current) leftForeArmRef.current.rotation.x = -0.15;
      if (rightForeArmRef.current) rightForeArmRef.current.rotation.x = -0.35;
      if (torsoRef.current) torsoRef.current.rotation.set(0, 0, 0);
      if (headRef.current) headRef.current.rotation.set(-0.04, Math.sin(t * 2.2) * 0.18, 0);
    } else if (poseMode === "pingpong") {
      if (leftThighRef.current) leftThighRef.current.rotation.x = 0.12;
      if (rightThighRef.current) rightThighRef.current.rotation.x = -0.12;
      if (leftCalfRef.current) leftCalfRef.current.rotation.x = 0.15;
      if (rightCalfRef.current) rightCalfRef.current.rotation.x = 0.15;
      if (leftArmRef.current) leftArmRef.current.rotation.set(-0.2, 0, 0.15);
      if (rightArmRef.current) {
        rightArmRef.current.rotation.set(-0.55 + Math.sin(t * 7) * 0.4, 0, -0.22);
      }
      if (leftForeArmRef.current) leftForeArmRef.current.rotation.x = -0.35;
      if (rightForeArmRef.current) {
        rightForeArmRef.current.rotation.x = -0.75 + Math.cos(t * 7) * 0.35;
      }
      if (torsoRef.current) torsoRef.current.rotation.set(0.08, Math.sin(t * 3.5) * 0.14, 0);
      if (headRef.current) headRef.current.rotation.set(0.04, Math.sin(t * 3.5) * 0.16, 0);
    } else if (poseMode === "coffee") {
      const sip = Math.max(0, Math.sin(t * 1.4));
      if (leftThighRef.current) leftThighRef.current.rotation.x = 0;
      if (rightThighRef.current) rightThighRef.current.rotation.x = 0;
      if (leftCalfRef.current) leftCalfRef.current.rotation.x = 0;
      if (rightCalfRef.current) rightCalfRef.current.rotation.x = 0;
      if (leftArmRef.current) leftArmRef.current.rotation.set(0, 0, 0.12);
      if (rightArmRef.current) {
        rightArmRef.current.rotation.set(-0.45 - sip * 0.35, 0, -0.1);
      }
      if (leftForeArmRef.current) leftForeArmRef.current.rotation.x = -0.15;
      if (rightForeArmRef.current) {
        rightForeArmRef.current.rotation.x = -1.05 - sip * 0.35;
      }
      if (torsoRef.current) torsoRef.current.rotation.set(0, Math.sin(t * 0.8) * 0.05, 0);
      if (headRef.current) headRef.current.rotation.set(-sip * 0.06, Math.sin(t * 0.9) * 0.14, 0);
    } else {
      const breath = Math.sin(t * 2.0);
      if (leftThighRef.current) leftThighRef.current.rotation.x = 0;
      if (rightThighRef.current) rightThighRef.current.rotation.x = 0;
      if (leftCalfRef.current) leftCalfRef.current.rotation.x = 0;
      if (rightCalfRef.current) rightCalfRef.current.rotation.x = 0;
      if (leftArmRef.current) leftArmRef.current.rotation.set(0, 0, 0.12 + breath * 0.02);
      if (rightArmRef.current) rightArmRef.current.rotation.set(0, 0, -0.12 - breath * 0.02);
      if (leftForeArmRef.current) leftForeArmRef.current.rotation.x = -0.14;
      if (rightForeArmRef.current) rightForeArmRef.current.rotation.x = -0.14;
      if (torsoRef.current) torsoRef.current.rotation.set(0, Math.sin(t * 0.65) * 0.05, 0);
      if (headRef.current) headRef.current.rotation.set(0, Math.sin(t * 0.85) * 0.14, 0);
    }
  });

  const shoulderX =
    spec.bottomType === "skirt_a" ||
    spec.bottomType === "skirt_pleated" ||
    spec.bottomType === "skirt_pencil"
      ? 0.16
      : 0.185;

  const legX =
    spec.bottomType === "skirt_a" ||
    spec.bottomType === "skirt_pleated" ||
    spec.bottomType === "skirt_pencil"
      ? 0.068
      : 0.082;

  const skirtBottomRadius =
    spec.bottomType === "skirt_a"
      ? 0.21
      : spec.bottomType === "skirt_pleated"
      ? 0.195
      : 0.155;

  return (
    <group scale={[spec.scale, spec.scale, spec.scale]}>
      <group ref={hipsRef} position={[0, 0.88, 0]}>
        {/* Female Skirt attached to hips */}
        {isSkirt && (
          <group ref={skirtRef} position={[0, -0.14, 0.01]}>
            <mesh>
              <cylinderGeometry args={[0.132, skirtBottomRadius, 0.34, 28, 1, false]} />
              <meshStandardMaterial color={spec.bottomColor} roughness={0.72} />
            </mesh>
          </group>
        )}

        {/* Left & Right Legs */}
        {[
          { thighRef: leftThighRef, calfRef: leftCalfRef, x: legX },
          { thighRef: rightThighRef, calfRef: rightCalfRef, x: -legX },
        ].map(({ thighRef, calfRef, x }, idx) => (
          <group key={idx} ref={thighRef} position={[x, 0, 0]}>
            <mesh position={[0, -0.18, 0]}>
              <capsuleGeometry args={[0.055, 0.27, 8, 12]} />
              <meshStandardMaterial
                color={isSkirt ? spec.skin : spec.bottomColor}
                roughness={0.68}
              />
            </mesh>
            <group ref={calfRef} position={[0, -0.37, 0]}>
              <mesh position={[0, -0.18, 0]}>
                <capsuleGeometry args={[0.044, 0.27, 8, 12]} />
                <meshStandardMaterial
                  color={isSkirt ? spec.skin : spec.bottomColor}
                  roughness={0.68}
                />
              </mesh>
              {/* Modern Low-Top Sneaker / Dress Shoe / Heel */}
              <RoundedBox
                args={[0.092, 0.055, 0.175]}
                radius={0.02}
                position={[0, -0.39, 0.03]}
              >
                <meshStandardMaterial color={spec.shoeColor} roughness={0.45} />
              </RoundedBox>
              <RoundedBox
                args={[0.096, 0.022, 0.18]}
                radius={0.008}
                position={[0, -0.422, 0.03]}
              >
                <meshStandardMaterial color={spec.soleColor} roughness={0.5} />
              </RoundedBox>
            </group>
          </group>
        ))}

        {/* Torso, Arms & Head */}
        <group ref={torsoRef}>
          <HumanTorsoOutfit role={role} spec={spec} />

          {/* Left & Right Arms (Short sleeve or rolled-cuff shirt + bare Asian forearms & hands) */}
          {[
            { armRef: leftArmRef, foreRef: leftForeArmRef, x: shoulderX, isRight: false },
            { armRef: rightArmRef, foreRef: rightForeArmRef, x: -shoulderX, isRight: true },
          ].map(({ armRef, foreRef, x, isRight }, idx) => (
            <group key={idx} ref={armRef} position={[x, 0.41, 0]}>
              {/* Sleeve Cap / Upper Arm */}
              <mesh position={[0, -0.06, 0]}>
                <capsuleGeometry args={[0.046, 0.09, 6, 10]} />
                <meshStandardMaterial color={spec.shirt} roughness={0.68} />
              </mesh>
              {/* Bare upper arm below short sleeve or rolled cuff */}
              <mesh position={[0, -0.16, 0]}>
                <capsuleGeometry args={[0.037, 0.12, 6, 10]} />
                <meshStandardMaterial
                  color={isShortSleeve ? spec.skin : spec.shirt}
                  roughness={0.58}
                />
              </mesh>
              {/* Rolled cuff ring for dress shirts */}
              {!isShortSleeve && (
                <mesh position={[0, -0.22, 0]} rotation={[Math.PI / 2, 0, 0]}>
                  <torusGeometry args={[0.039, 0.009, 6, 14]} />
                  <meshStandardMaterial color={spec.shirt} roughness={0.6} />
                </mesh>
              )}

              {/* Bare Warm Asian Forearm & Visible Hand */}
              <group ref={foreRef} position={[0, -0.25, 0]}>
                <mesh position={[0, -0.11, 0]}>
                  <capsuleGeometry args={[0.033, 0.16, 6, 10]} />
                  <meshStandardMaterial color={forearmColor} roughness={0.48} />
                </mesh>
                <RoundedBox
                  args={[0.048, 0.068, 0.034]}
                  radius={0.014}
                  position={[0, -0.24, 0.008]}
                >
                  <meshStandardMaterial color={spec.skin} roughness={0.48} />
                </RoundedBox>

                {/* Takeaway Coffee Cup when in Canteen coffee pose */}
                {isRight && poseMode === "coffee" && (
                  <group position={[0, -0.24, 0.05]} rotation={[0.45, 0, 0]}>
                    <mesh>
                      <cylinderGeometry args={[0.036, 0.028, 0.095, 14]} />
                      <meshStandardMaterial color="#f8fafc" roughness={0.3} />
                    </mesh>
                    <mesh position={[0, 0.052, 0]}>
                      <cylinderGeometry args={[0.038, 0.038, 0.015, 14]} />
                      <meshStandardMaterial color="#18181b" />
                    </mesh>
                  </group>
                )}
              </group>
            </group>
          ))}

          {/* Neck */}
          <mesh position={[0, 0.49, 0]}>
            <cylinderGeometry args={[0.045, 0.052, 0.09, 12]} />
            <meshStandardMaterial color={spec.skin} roughness={0.48} />
          </mesh>

          {/* Natural Proportioned Asian Head & Face */}
          <group ref={headRef} position={[0, 0.62, 0]}>
            <mesh scale={[0.92, 1.08, 0.96]}>
              <sphereGeometry args={[0.115, 24, 18]} />
              <meshStandardMaterial color={spec.skin} roughness={0.48} />
            </mesh>
            {/* Ears */}
            {[-0.105, 0.105].map((ex, i) => (
              <mesh key={i} position={[ex, -0.005, -0.005]} scale={[0.6, 1.0, 0.65]}>
                <sphereGeometry args={[0.02, 10, 8]} />
                <meshStandardMaterial color={spec.skin} roughness={0.5} />
              </mesh>
            ))}
            {/* Almond Asian Eyes & Eyebrows */}
            {[-0.036, 0.036].map((ex, i) => (
              <group key={i} position={[ex, 0.008, 0.102]}>
                <mesh scale={[1.15, 0.72, 0.5]}>
                  <sphereGeometry args={[0.014, 10, 8]} />
                  <meshStandardMaterial color="#ffffff" />
                </mesh>
                <mesh position={[0, 0, 0.004]}>
                  <sphereGeometry args={[0.0085, 10, 8]} />
                  <meshStandardMaterial color="#18181b" roughness={0.2} />
                </mesh>
                <mesh position={[0.003, 0.003, 0.01]}>
                  <sphereGeometry args={[0.0028, 6, 6]} />
                  <meshBasicMaterial color="#ffffff" />
                </mesh>
                <mesh position={[0, 0.022, 0.002]}>
                  <boxGeometry args={[0.028, 0.006, 0.006]} />
                  <meshStandardMaterial color={spec.hair} />
                </mesh>
              </group>
            ))}
            {/* Nose & Warm Lips */}
            <mesh position={[0, -0.014, 0.114]} scale={[0.8, 1.1, 0.9]}>
              <sphereGeometry args={[0.01, 8, 8]} />
              <meshStandardMaterial color={spec.skin} roughness={0.5} />
            </mesh>
            <mesh position={[0, -0.044, 0.103]}>
              <boxGeometry args={[0.03, 0.008, 0.008]} />
              <meshStandardMaterial color="#c97b6d" roughness={0.45} />
            </mesh>

            <AsianHairStyle role={role} color={spec.hair} />
          </group>
        </group>
      </group>
    </group>
  );
}
