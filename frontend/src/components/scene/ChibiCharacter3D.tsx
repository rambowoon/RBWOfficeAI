import { RoundedBox } from "@react-three/drei";
import { useFrame } from "@react-three/fiber";
import { useMemo, useRef } from "react";
import * as THREE from "three";
import type { AgentRole } from "../../types";

export type ChibiPoseMode =
  | "walk"
  | "work"
  | "sit"
  | "coffee"
  | "pingpong"
  | "alert"
  | "done"
  | "stand";

interface ChibiCharacter3DProps {
  role: AgentRole;
  poseMode: ChibiPoseMode;
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

function useSculptedChibiHeadGeometry(): THREE.SphereGeometry {
  return useMemo(() => {
    const geom = new THREE.SphereGeometry(0.28, 36, 28);
    const pos = geom.attributes.position;
    for (let i = 0; i < pos.count; i++) {
      let x = pos.getX(i);
      let y = pos.getY(i);
      let z = pos.getZ(i);

      // Gentle wider cheek puff & softer lower chin for Pixar-chibi silhouette
      if (y < 0.04 && y > -0.18 && z > -0.05) {
        const cheekFactor = 1.0 + 0.085 * Math.cos(((y + 0.07) / 0.12) * Math.PI * 0.5);
        x *= cheekFactor;
        z *= 1.03;
      }
      if (y < -0.16) {
        x *= 0.92;
        z *= 0.92;
      }
      pos.setXYZ(i, x, y, z);
    }
    geom.computeVertexNormals();
    return geom;
  }, []);
}

function ChibiEyesAndFace({
  irisColor,
  coolPout = false,
  hasEyelashes = false,
}: {
  irisColor: string;
  coolPout?: boolean;
  hasEyelashes?: boolean;
}) {
  return (
    <group>
      {/* Left & Right Glossy Pixar Eyes */}
      {[-0.092, 0.092].map((ex, i) => {
        const isLeft = i === 0;
        return (
          <group
            key={i}
            position={[ex, 0.012, 0.252]}
            rotation={[0, isLeft ? -0.14 : 0.14, 0]}
          >
            {/* White Sclera */}
            <mesh scale={[1.0, 1.18, 0.42]}>
              <sphereGeometry args={[0.056, 20, 16]} />
              <meshStandardMaterial color="#ffffff" roughness={0.18} />
            </mesh>
            {/* Large Colored Iris */}
            <mesh position={[0, -0.002, 0.017]} scale={[1.0, 1.12, 0.45]}>
              <sphereGeometry args={[0.041, 18, 16]} />
              <meshPhysicalMaterial
                color={irisColor}
                roughness={0.15}
                clearcoat={0.75}
              />
            </mesh>
            {/* Deep Pupil */}
            <mesh position={[0, -0.002, 0.025]} scale={[1.0, 1.08, 0.45]}>
              <sphereGeometry args={[0.023, 14, 12]} />
              <meshStandardMaterial color="#090d16" roughness={0.1} />
            </mesh>
            {/* Two Specular Catchlights */}
            <mesh position={[0.014, 0.017, 0.036]}>
              <sphereGeometry args={[0.011, 10, 10]} />
              <meshBasicMaterial color="#ffffff" />
            </mesh>
            <mesh position={[-0.012, -0.014, 0.035]}>
              <sphereGeometry args={[0.0055, 8, 8]} />
              <meshBasicMaterial color="#ffffff" />
            </mesh>
            {/* Upper Eyelash Arch */}
            <mesh
              position={[0, 0.042, 0.01]}
              rotation={[0.25, 0, isLeft ? 0.1 : -0.1]}
            >
              <torusGeometry args={[0.052, hasEyelashes ? 0.009 : 0.0065, 8, 18, Math.PI]} />
              <meshStandardMaterial color="#1c1917" roughness={0.5} />
            </mesh>
            {/* Expressive Eyebrow */}
            <RoundedBox
              args={[0.088, 0.018, 0.018]}
              radius={0.007}
              position={[0, 0.082, 0.006]}
              rotation={[0, 0, isLeft ? 0.08 : -0.08]}
            >
              <meshStandardMaterial color="#271911" roughness={0.6} />
            </RoundedBox>
          </group>
        );
      })}

      {/* Button Nose */}
      <mesh position={[0, -0.038, 0.285]} scale={[1.15, 0.85, 0.9]}>
        <sphereGeometry args={[0.024, 14, 12]} />
        <meshPhysicalMaterial color="#f5b895" roughness={0.4} clearcoat={0.15} />
      </mesh>

      {/* Rosy Cheek Blush */}
      {[-0.145, 0.145].map((cx, i) => (
        <mesh
          key={i}
          position={[cx, -0.062, 0.242]}
          rotation={[0, i === 0 ? -0.45 : 0.45, 0]}
          scale={[1.3, 0.8, 0.35]}
        >
          <sphereGeometry args={[0.036, 12, 10]} />
          <meshStandardMaterial color="#fda4af" transparent opacity={0.48} roughness={0.7} />
        </mesh>
      ))}

      {/* Mouth: Cheerful Open Smile or Cute Cool Pout */}
      {coolPout ? (
        <RoundedBox
          args={[0.042, 0.012, 0.016]}
          radius={0.005}
          position={[0, -0.108, 0.266]}
        >
          <meshStandardMaterial color="#e07a7a" roughness={0.4} />
        </RoundedBox>
      ) : (
        <group position={[0, -0.105, 0.258]} rotation={[0.18, 0, 0]}>
          <mesh rotation={[0, 0, Math.PI]}>
            <torusGeometry args={[0.056, 0.014, 8, 18, Math.PI]} />
            <meshStandardMaterial color="#9f1239" roughness={0.4} />
          </mesh>
          <RoundedBox args={[0.078, 0.022, 0.018]} radius={0.006} position={[0, -0.005, 0.006]}>
            <meshStandardMaterial color="#ffffff" roughness={0.2} />
          </RoundedBox>
          <mesh position={[0, -0.026, 0.004]} scale={[1.1, 0.65, 0.6]}>
            <sphereGeometry args={[0.026, 10, 8]} />
            <meshStandardMaterial color="#fb7185" roughness={0.5} />
          </mesh>
        </group>
      )}
    </group>
  );
}

function ChibiHairAndHeadwear({ role }: { role: AgentRole }) {
  if (role === "leader") {
    // Image 1: Swept-up voluminous dark-brown Pompadour
    const hairColor = "#291811";
    return (
      <group>
        <mesh position={[0, 0.04, -0.02]}>
          <sphereGeometry args={[0.292, 24, 18, 0, Math.PI * 2, 0, Math.PI * 0.56]} />
          <meshPhysicalMaterial color={hairColor} roughness={0.35} clearcoat={0.25} />
        </mesh>
        {[
          { pos: [0, 0.25, 0.07] as [number, number, number], rot: [-0.45, 0, 0] as [number, number, number], s: [1.15, 0.72, 1.35] as [number, number, number] },
          { pos: [-0.08, 0.23, 0.08] as [number, number, number], rot: [-0.35, 0.15, 0.22] as [number, number, number], s: [0.85, 0.68, 1.25] as [number, number, number] },
          { pos: [0.08, 0.24, 0.08] as [number, number, number], rot: [-0.4, -0.15, -0.22] as [number, number, number], s: [0.85, 0.72, 1.25] as [number, number, number] },
          { pos: [0.02, 0.29, -0.02] as [number, number, number], rot: [-0.25, 0, -0.1] as [number, number, number], s: [1.05, 0.65, 1.35] as [number, number, number] },
          { pos: [-0.15, 0.15, -0.03] as [number, number, number], rot: [0, 0, 0.35] as [number, number, number], s: [0.65, 0.85, 1.0] as [number, number, number] },
          { pos: [0.15, 0.15, -0.03] as [number, number, number], rot: [0, 0, -0.35] as [number, number, number], s: [0.65, 0.85, 1.0] as [number, number, number] },
        ].map((lock, i) => (
          <mesh key={i} position={lock.pos} rotation={lock.rot} scale={lock.s}>
            <sphereGeometry args={[0.125, 16, 14]} />
            <meshPhysicalMaterial color={hairColor} roughness={0.34} clearcoat={0.28} />
          </mesh>
        ))}
      </group>
    );
  }

  if (role === "asset") {
    // Image 2: Voluminous wavy chestnut-brown hair + cream/gold headband
    const hairColor = "#5c3317";
    return (
      <group>
        <mesh position={[0, 0.03, -0.02]}>
          <sphereGeometry args={[0.305, 24, 20, 0, Math.PI * 2, 0, Math.PI * 0.65]} />
          <meshPhysicalMaterial color={hairColor} roughness={0.36} clearcoat={0.22} />
        </mesh>
        {/* Front Side-Swept Bangs */}
        <mesh position={[-0.1, 0.18, 0.18]} rotation={[0.25, 0.3, 0.35]} scale={[1.2, 0.65, 0.7]}>
          <sphereGeometry args={[0.12, 16, 12]} />
          <meshPhysicalMaterial color={hairColor} roughness={0.36} />
        </mesh>
        <mesh position={[0.11, 0.18, 0.17]} rotation={[0.25, -0.35, -0.35]} scale={[1.15, 0.65, 0.7]}>
          <sphereGeometry args={[0.115, 16, 12]} />
          <meshPhysicalMaterial color={hairColor} roughness={0.36} />
        </mesh>
        {/* Wavy Shoulder Fluff */}
        {[-0.22, 0.22].map((hx, idx) => (
          <mesh key={idx} position={[hx, -0.1, -0.08]} scale={[0.9, 1.35, 0.95]}>
            <sphereGeometry args={[0.14, 16, 14]} />
            <meshPhysicalMaterial color={hairColor} roughness={0.38} />
          </mesh>
        ))}
        <mesh position={[0, -0.08, -0.22]} scale={[1.55, 1.35, 0.8]}>
          <sphereGeometry args={[0.18, 16, 14]} />
          <meshPhysicalMaterial color={hairColor} roughness={0.38} />
        </mesh>
        {/* Cream Headband */}
        <mesh position={[0, 0.07, 0.03]} rotation={[-0.28, Math.PI / 2, 0]}>
          <torusGeometry args={[0.295, 0.022, 10, 28, Math.PI]} />
          <meshPhysicalMaterial color="#fde68a" roughness={0.3} clearcoat={0.3} />
        </mesh>
      </group>
    );
  }

  if (role === "dev" || role === "ui_dev_2") {
    // Image 3: Flowing Pastel-Pink Hair
    const pinkHair = "#f472b6";
    return (
      <group>
        <mesh position={[0, 0.04, -0.02]}>
          <sphereGeometry args={[0.305, 24, 20, 0, Math.PI * 2, 0, Math.PI * 0.62]} />
          <meshPhysicalMaterial color={pinkHair} roughness={0.32} clearcoat={0.28} />
        </mesh>
        <mesh position={[0.07, 0.19, 0.17]} rotation={[0.2, -0.3, -0.35]} scale={[1.35, 0.75, 0.75]}>
          <sphereGeometry args={[0.135, 16, 12]} />
          <meshPhysicalMaterial color={pinkHair} roughness={0.32} />
        </mesh>
        <mesh position={[-0.12, 0.16, 0.16]} rotation={[0.2, 0.35, 0.4]} scale={[1.1, 0.7, 0.7]}>
          <sphereGeometry args={[0.115, 16, 12]} />
          <meshPhysicalMaterial color={pinkHair} roughness={0.32} />
        </mesh>
        {/* Sweeping Back Flare */}
        <mesh position={[0, -0.08, -0.22]} scale={[1.65, 1.4, 0.85]}>
          <sphereGeometry args={[0.19, 18, 14]} />
          <meshPhysicalMaterial color={pinkHair} roughness={0.34} />
        </mesh>
        <mesh position={[-0.26, -0.14, -0.14]} rotation={[0, 0, -0.45]} scale={[0.9, 1.35, 0.75]}>
          <sphereGeometry args={[0.13, 14, 12]} />
          <meshPhysicalMaterial color={pinkHair} roughness={0.34} />
        </mesh>
        <mesh position={[0.26, -0.14, -0.14]} rotation={[0, 0, 0.45]} scale={[0.9, 1.35, 0.75]}>
          <sphereGeometry args={[0.13, 14, 12]} />
          <meshPhysicalMaterial color={pinkHair} roughness={0.34} />
        </mesh>
      </group>
    );
  }

  if (role === "ui_dev_1") {
    // Image 4: Multi-layered Spiky Anime Hair
    const hairColor = "#3b2314";
    const spikes: Array<{ pos: [number, number, number]; rot: [number, number, number]; r: number; h: number }> = [
      { pos: [0, 0.32, 0.04], rot: [0.15, 0, 0], r: 0.095, h: 0.22 },
      { pos: [-0.11, 0.29, 0.06], rot: [0.22, 0, 0.42], r: 0.085, h: 0.2 },
      { pos: [0.11, 0.29, 0.06], rot: [0.22, 0, -0.42], r: 0.085, h: 0.2 },
      { pos: [-0.19, 0.2, 0.05], rot: [0.15, 0, 0.75], r: 0.075, h: 0.18 },
      { pos: [0.19, 0.2, 0.05], rot: [0.15, 0, -0.75], r: 0.075, h: 0.18 },
      { pos: [0, 0.27, -0.12], rot: [-0.5, 0, 0], r: 0.095, h: 0.22 },
      { pos: [-0.13, 0.22, -0.11], rot: [-0.45, 0, 0.48], r: 0.08, h: 0.19 },
      { pos: [0.13, 0.22, -0.11], rot: [-0.45, 0, -0.48], r: 0.08, h: 0.19 },
      { pos: [-0.07, 0.21, 0.18], rot: [0.65, 0, 0.25], r: 0.065, h: 0.15 },
      { pos: [0.07, 0.21, 0.18], rot: [0.65, 0, -0.25], r: 0.065, h: 0.15 },
    ];
    return (
      <group>
        <mesh position={[0, 0.04, -0.02]}>
          <sphereGeometry args={[0.294, 22, 16, 0, Math.PI * 2, 0, Math.PI * 0.56]} />
          <meshPhysicalMaterial color={hairColor} roughness={0.36} clearcoat={0.2} />
        </mesh>
        {spikes.map((sp, i) => (
          <mesh key={i} position={sp.pos} rotation={sp.rot}>
            <coneGeometry args={[sp.r, sp.h, 12]} />
            <meshPhysicalMaterial color={hairColor} roughness={0.36} clearcoat={0.22} />
          </mesh>
        ))}
      </group>
    );
  }

  if (role === "seeder") {
    // Image 5: Cream Baseball Cap + Brown Hair Bangs + Large Round Brown-Tinted Sunglasses
    const capColor = "#e7e5e4";
    const hairColor = "#452817";
    return (
      <group>
        {/* Fringe bangs peeking below cap */}
        <mesh position={[0, 0.12, 0.19]} scale={[1.6, 0.55, 0.7]}>
          <sphereGeometry args={[0.11, 14, 10]} />
          <meshStandardMaterial color={hairColor} roughness={0.5} />
        </mesh>
        {/* Baseball Cap Dome */}
        <mesh position={[0, 0.08, -0.01]} rotation={[-0.14, 0, 0]}>
          <sphereGeometry args={[0.305, 24, 18, 0, Math.PI * 2, 0, Math.PI * 0.54]} />
          <meshPhysicalMaterial color={capColor} roughness={0.65} />
        </mesh>
        {/* Cap Top Button */}
        <mesh position={[0, 0.38, -0.05]}>
          <sphereGeometry args={[0.022, 10, 8]} />
          <meshStandardMaterial color="#a8a29e" />
        </mesh>
        {/* Curved Visor Brim */}
        <mesh
          position={[0, 0.14, 0.25]}
          rotation={[0.2, 0, 0]}
          scale={[1.05, 0.18, 0.85]}
        >
          <cylinderGeometry args={[0.25, 0.26, 0.08, 22, 1, false, -Math.PI * 0.45, Math.PI * 0.9]} />
          <meshStandardMaterial color={capColor} roughness={0.65} />
        </mesh>
        {/* Dark "BEI" Front Cap Emblem */}
        <RoundedBox args={[0.13, 0.052, 0.015]} radius={0.006} position={[0, 0.255, 0.265]} rotation={[-0.35, 0, 0]}>
          <meshStandardMaterial color="#1c1917" />
        </RoundedBox>
        {/* Large Round Brown-Tinted Wire-Frame Sunglasses */}
        <group position={[0, 0.012, 0.295]}>
          {[-0.092, 0.092].map((gx, i) => (
            <group key={i} position={[gx, 0, 0]} rotation={[0, i === 0 ? -0.14 : 0.14, 0]}>
              <mesh>
                <torusGeometry args={[0.072, 0.0065, 8, 24]} />
                <meshStandardMaterial color="#d4d4d8" metalness={0.85} roughness={0.2} />
              </mesh>
              <mesh scale={[1, 1, 0.25]}>
                <sphereGeometry args={[0.068, 18, 14]} />
                <meshPhysicalMaterial
                  color="#451a03"
                  transparent
                  opacity={0.78}
                  roughness={0.1}
                  clearcoat={0.9}
                />
              </mesh>
            </group>
          ))}
          <mesh position={[0, 0.018, 0.01]}>
            <boxGeometry args={[0.045, 0.009, 0.009]} />
            <meshStandardMaterial color="#d4d4d8" metalness={0.85} />
          </mesh>
        </group>
      </group>
    );
  }

  if (role === "config") {
    // Cyan Tech Headset + Dark Spiky Fade Hair
    const hairColor = "#1e293b";
    return (
      <group>
        <mesh position={[0, 0.04, -0.02]}>
          <sphereGeometry args={[0.292, 22, 16, 0, Math.PI * 2, 0, Math.PI * 0.54]} />
          <meshPhysicalMaterial color={hairColor} roughness={0.4} />
        </mesh>
        {[-0.07, 0, 0.07].map((sx, i) => (
          <mesh key={i} position={[sx, 0.3, 0.04]} rotation={[0.2, 0, -sx * 2]}>
            <coneGeometry args={[0.075, 0.17, 10]} />
            <meshPhysicalMaterial color={hairColor} roughness={0.38} />
          </mesh>
        ))}
        {/* Over-Ear Cyan Headset */}
        <mesh position={[0, 0.06, 0]} rotation={[0, Math.PI / 2, 0]}>
          <torusGeometry args={[0.31, 0.02, 8, 24, Math.PI]} />
          <meshStandardMaterial color="#0f172a" metalness={0.5} />
        </mesh>
        {[-0.305, 0.305].map((hx, idx) => (
          <mesh key={idx} position={[hx, 0.01, 0]} rotation={[0, 0, Math.PI / 2]}>
            <cylinderGeometry args={[0.075, 0.075, 0.055, 14]} />
            <meshStandardMaterial color="#06b6d4" emissive="#06b6d4" emissiveIntensity={0.3} />
          </mesh>
        ))}
      </group>
    );
  }

  // QA (Tuấn - Male): Short dark crop + thin dark glasses
  const hairColor = "#0f172a";
  return (
    <group>
      <mesh position={[0, 0.04, -0.02]}>
        <sphereGeometry args={[0.292, 22, 16, 0, Math.PI * 2, 0, Math.PI * 0.54]} />
        <meshPhysicalMaterial color={hairColor} roughness={0.4} />
      </mesh>
      <RoundedBox
        args={[0.24, 0.08, 0.12]}
        radius={0.03}
        position={[0, 0.21, 0.18]}
        rotation={[0.28, 0, 0]}
      >
        <meshPhysicalMaterial color={hairColor} roughness={0.38} />
      </RoundedBox>
      {/* Thin Frame Glasses */}
      <group position={[0, 0.012, 0.29]}>
        {[-0.09, 0.09].map((gx, i) => (
          <mesh key={i} position={[gx, 0, 0]}>
            <torusGeometry args={[0.062, 0.006, 8, 20]} />
            <meshStandardMaterial color="#0f172a" metalness={0.6} />
          </mesh>
        ))}
        <mesh position={[0, 0.015, 0]}>
          <boxGeometry args={[0.05, 0.008, 0.008]} />
          <meshStandardMaterial color="#0f172a" />
        </mesh>
      </group>
    </group>
  );
}

function ChibiTorsoOutfit({ role }: { role: AgentRole }) {
  if (role === "leader") {
    // Image 1: Steel-Blue Suit Jacket, White Shirt, Orange/Navy Striped Tie, Black Belt
    return (
      <group>
        <RoundedBox args={[0.31, 0.34, 0.21]} radius={0.075} position={[0, 0.17, 0]}>
          <meshPhysicalMaterial color="#47668e" roughness={0.45} clearcoat={0.1} />
        </RoundedBox>
        {/* White Dress Shirt Front */}
        <RoundedBox args={[0.12, 0.26, 0.215]} radius={0.03} position={[0, 0.2, 0.008]}>
          <meshStandardMaterial color="#ffffff" roughness={0.35} />
        </RoundedBox>
        {/* Striped Orange/Navy Tie */}
        <RoundedBox args={[0.044, 0.2, 0.02]} radius={0.008} position={[0, 0.17, 0.115]}>
          <meshStandardMaterial color="#ea580c" roughness={0.4} />
        </RoundedBox>
        {/* Black Waist Belt + Silver Buckle */}
        <RoundedBox args={[0.318, 0.042, 0.22]} radius={0.01} position={[0, 0.025, 0]}>
          <meshStandardMaterial color="#0f172a" roughness={0.3} />
        </RoundedBox>
        <mesh position={[0, 0.025, 0.115]}>
          <boxGeometry args={[0.055, 0.036, 0.012]} />
          <meshStandardMaterial color="#e2e8f0" metalness={0.85} />
        </mesh>
      </group>
    );
  }

  if (role === "asset") {
    // Image 2: Sky-Blue Dress, White Peter-Pan Collar, Brown Belt & Flared Skirt
    return (
      <group>
        <RoundedBox args={[0.27, 0.3, 0.19]} radius={0.07} position={[0, 0.19, 0]}>
          <meshPhysicalMaterial color="#60a5fa" roughness={0.42} />
        </RoundedBox>
        {/* White Peter-Pan Collar */}
        {[-0.045, 0.045].map((cx, i) => (
          <mesh key={i} position={[cx, 0.33, 0.06]} rotation={[0.35, 0, i === 0 ? 0.25 : -0.25]} scale={[1.2, 0.65, 0.9]}>
            <sphereGeometry args={[0.045, 12, 10]} />
            <meshStandardMaterial color="#ffffff" />
          </mesh>
        ))}
        {/* Brown Belt */}
        <RoundedBox args={[0.28, 0.042, 0.2]} radius={0.012} position={[0, 0.06, 0]}>
          <meshStandardMaterial color="#b45309" roughness={0.45} />
        </RoundedBox>
        {/* Flared A-line Skirt */}
        <mesh position={[0, -0.05, 0]}>
          <cylinderGeometry args={[0.145, 0.235, 0.22, 24]} />
          <meshPhysicalMaterial color="#60a5fa" roughness={0.45} />
        </mesh>
      </group>
    );
  }

  if (role === "dev" || role === "ui_dev_2") {
    // Image 3: White Shirt, Navy Vest, Cyan Tie, Navy Pencil Skirt
    return (
      <group>
        <RoundedBox args={[0.27, 0.3, 0.19]} radius={0.07} position={[0, 0.19, 0]}>
          <meshPhysicalMaterial color="#334155" roughness={0.45} />
        </RoundedBox>
        <RoundedBox args={[0.11, 0.24, 0.195]} radius={0.025} position={[0, 0.22, 0.008]}>
          <meshStandardMaterial color="#ffffff" />
        </RoundedBox>
        <RoundedBox args={[0.04, 0.18, 0.018]} radius={0.006} position={[0, 0.19, 0.105]}>
          <meshStandardMaterial color="#06b6d4" />
        </RoundedBox>
        {/* Pencil Skirt */}
        <mesh position={[0, -0.02, 0]}>
          <cylinderGeometry args={[0.145, 0.165, 0.19, 20]} />
          <meshPhysicalMaterial color="#1e293b" roughness={0.48} />
        </mesh>
      </group>
    );
  }

  if (role === "seeder") {
    // Image 5: Oversized Dove-Grey Sweatshirt + Dark Crossbody Messenger Bag
    return (
      <group>
        <RoundedBox args={[0.34, 0.35, 0.24]} radius={0.09} position={[0, 0.17, 0]}>
          <meshPhysicalMaterial color="#cbd5e1" roughness={0.55} />
        </RoundedBox>
        {/* Ribbed Hem & Collar */}
        <mesh position={[0, 0.34, 0]} rotation={[Math.PI / 2, 0, 0]}>
          <torusGeometry args={[0.095, 0.02, 8, 18]} />
          <meshStandardMaterial color="#94a3b8" />
        </mesh>
        {/* Crossbody Bag Strap */}
        <mesh position={[0, 0.17, 0.005]} rotation={[0, 0, -0.78]}>
          <boxGeometry args={[0.045, 0.44, 0.25]} />
          <meshStandardMaterial color="#1e293b" roughness={0.5} />
        </mesh>
        {/* Crossbody Bag Pouch at Hip */}
        <RoundedBox args={[0.16, 0.15, 0.08]} radius={0.025} position={[0.17, 0.03, 0.06]} rotation={[0, 0.3, 0]}>
          <meshStandardMaterial color="#0f172a" roughness={0.45} />
        </RoundedBox>
      </group>
    );
  }

  if (role === "ui_dev_1" || role === "config") {
    // Image 4: Open Zip Hoodie (Orange for UI1, Cyan for Config) over White Tee + Backpack Straps
    const hoodieColor = role === "ui_dev_1" ? "#f97316" : "#0891b2";
    return (
      <group>
        <RoundedBox args={[0.32, 0.34, 0.22]} radius={0.08} position={[0, 0.17, 0]}>
          <meshPhysicalMaterial color={hoodieColor} roughness={0.45} />
        </RoundedBox>
        {/* White Inner T-shirt & Hoodie Bottom Trim */}
        <RoundedBox args={[0.13, 0.32, 0.226]} radius={0.03} position={[0, 0.17, 0.008]}>
          <meshStandardMaterial color="#ffffff" />
        </RoundedBox>
        <RoundedBox args={[0.326, 0.045, 0.226]} radius={0.015} position={[0, 0.025, 0]}>
          <meshStandardMaterial color="#ffffff" />
        </RoundedBox>
        {/* Hoodie Collar */}
        <mesh position={[0, 0.33, -0.02]} rotation={[Math.PI / 2, 0, 0]}>
          <torusGeometry args={[0.115, 0.035, 10, 18]} />
          <meshStandardMaterial color={hoodieColor} />
        </mesh>
        {/* Backpack Straps */}
        {[-0.1, 0.1].map((sx, i) => (
          <mesh key={i} position={[sx, 0.19, 0]}>
            <boxGeometry args={[0.035, 0.31, 0.232]} />
            <meshStandardMaterial color="#18181b" />
          </mesh>
        ))}
      </group>
    );
  }

  // QA (Tuấn - Male): Open Cyan/Slate Jacket + White Tee + Dark Belt
  return (
    <group>
      <RoundedBox args={[0.31, 0.34, 0.21]} radius={0.075} position={[0, 0.17, 0]}>
        <meshPhysicalMaterial color="#0ea5e9" roughness={0.45} />
      </RoundedBox>
      <RoundedBox args={[0.12, 0.31, 0.216]} radius={0.03} position={[0, 0.17, 0.008]}>
        <meshStandardMaterial color="#ffffff" />
      </RoundedBox>
      <RoundedBox args={[0.318, 0.042, 0.22]} radius={0.01} position={[0, 0.025, 0]}>
        <meshStandardMaterial color="#1e293b" roughness={0.4} />
      </RoundedBox>
    </group>
  );
}

export function ChibiCharacter3D({
  role,
  poseMode,
  isMoving,
}: ChibiCharacter3DProps) {
  const hipsRef = useRef<THREE.Group>(null);
  const torsoRef = useRef<THREE.Group>(null);
  const headRef = useRef<THREE.Group>(null);
  const leftArmRef = useRef<THREE.Group>(null);
  const rightArmRef = useRef<THREE.Group>(null);
  const leftForeArmRef = useRef<THREE.Group>(null);
  const rightForeArmRef = useRef<THREE.Group>(null);
  const leftThighRef = useRef<THREE.Group>(null);
  const rightThighRef = useRef<THREE.Group>(null);
  const leftCalfRef = useRef<THREE.Group>(null);
  const rightCalfRef = useRef<THREE.Group>(null);

  const headGeom = useSculptedChibiHeadGeometry();
  const timeOffset = ROLE_ORDER[role] * 1.43;

  const palette = useMemo(() => {
    switch (role) {
      case "leader":
        return {
          skin: "#fde0c8",
          iris: "#5c3317",
          sleeve: "#47668e",
          pants: "#47668e",
          shoe: "#18181b",
          sole: "#18181b",
          shorts: false,
          skirtSkinLegs: false,
          lashes: false,
          pout: false,
        };
      case "asset":
        return {
          skin: "#ffe4d0",
          iris: "#6b3e1b",
          sleeve: "#60a5fa",
          pants: "#ffe4d0",
          shoe: "#dc2626",
          sole: "#dc2626",
          shorts: false,
          skirtSkinLegs: true,
          lashes: true,
          pout: false,
        };
      case "dev":
      case "ui_dev_2":
        return {
          skin: "#ffe4d0",
          iris: "#4d7c0f",
          sleeve: "#ffffff",
          pants: "#ffe4d0",
          shoe: "#1e293b",
          sole: "#1e293b",
          shorts: false,
          skirtSkinLegs: true,
          lashes: true,
          pout: false,
        };
      case "ui_dev_1":
        return {
          skin: "#fddcc2",
          iris: "#5c3317",
          sleeve: "#f97316",
          pants: "#1f2937",
          shoe: "#f97316",
          sole: "#ffffff",
          shorts: true,
          skirtSkinLegs: false,
          lashes: false,
          pout: false,
        };
      case "seeder":
        return {
          skin: "#fde2cc",
          iris: "#432818",
          sleeve: "#cbd5e1",
          pants: "#f5f5f4",
          shoe: "#e2e8f0",
          sole: "#ffffff",
          shorts: false,
          skirtSkinLegs: false,
          lashes: false,
          pout: true,
        };
      case "config":
        return {
          skin: "#fad6ba",
          iris: "#0369a1",
          sleeve: "#0891b2",
          pants: "#1e293b",
          shoe: "#0891b2",
          sole: "#ffffff",
          shorts: false,
          skirtSkinLegs: false,
          lashes: false,
          pout: false,
        };
      case "qa":
        return {
          skin: "#fad6ba",
          iris: "#0369a1",
          sleeve: "#0ea5e9",
          pants: "#1e293b",
          shoe: "#1e293b",
          sole: "#ffffff",
          shorts: false,
          skirtSkinLegs: false,
          lashes: false,
          pout: false,
        };
    }
  }, [role]);

  useFrame((state) => {
    const t = state.clock.elapsedTime + timeOffset;
    const isSeated = !isMoving && (poseMode === "work" || poseMode === "sit");

    if (hipsRef.current) {
      const targetHipY = isSeated
        ? 0.4
        : isMoving || poseMode === "walk"
        ? 0.44 + Math.abs(Math.sin(t * 9.5)) * 0.045
        : 0.44 + Math.sin(t * 2.1) * 0.01;
      hipsRef.current.position.y = THREE.MathUtils.lerp(
        hipsRef.current.position.y,
        targetHipY,
        0.2
      );
    }

    if (isMoving || poseMode === "walk") {
      const stride = Math.sin(t * 9.5);
      const kneeL = Math.max(0, -Math.cos(t * 9.5)) * 0.7;
      const kneeR = Math.max(0, Math.cos(t * 9.5)) * 0.7;
      if (leftThighRef.current) leftThighRef.current.rotation.x = stride * 0.62;
      if (rightThighRef.current) rightThighRef.current.rotation.x = -stride * 0.62;
      if (leftCalfRef.current) leftCalfRef.current.rotation.x = kneeL;
      if (rightCalfRef.current) rightCalfRef.current.rotation.x = kneeR;

      if (leftArmRef.current) {
        leftArmRef.current.rotation.x = -stride * 0.55;
        leftArmRef.current.rotation.z = 0.16;
      }
      if (rightArmRef.current) {
        rightArmRef.current.rotation.x = stride * 0.55;
        rightArmRef.current.rotation.z = -0.16;
      }
      if (leftForeArmRef.current) leftForeArmRef.current.rotation.x = -0.25;
      if (rightForeArmRef.current) rightForeArmRef.current.rotation.x = -0.25;
      if (torsoRef.current) {
        torsoRef.current.rotation.x = 0.06;
        torsoRef.current.rotation.y = stride * 0.08;
      }
      if (headRef.current) {
        headRef.current.rotation.set(0.02, 0, Math.sin(t * 9.5) * 0.05);
      }
    } else if (poseMode === "work") {
      // Seated neatly in office chair typing on dual-monitor desk
      const typeL = Math.sin(t * 14) * 0.18;
      const typeR = Math.cos(t * 14) * 0.18;
      if (leftThighRef.current) leftThighRef.current.rotation.x = -1.38;
      if (rightThighRef.current) rightThighRef.current.rotation.x = -1.38;
      if (leftCalfRef.current) leftCalfRef.current.rotation.x = 1.38;
      if (rightCalfRef.current) rightCalfRef.current.rotation.x = 1.38;

      if (leftArmRef.current) {
        leftArmRef.current.rotation.x = -0.78;
        leftArmRef.current.rotation.z = 0.06;
      }
      if (rightArmRef.current) {
        rightArmRef.current.rotation.x = -0.78;
        rightArmRef.current.rotation.z = -0.06;
      }
      if (leftForeArmRef.current) leftForeArmRef.current.rotation.x = -0.68 + typeL;
      if (rightForeArmRef.current) rightForeArmRef.current.rotation.x = -0.68 + typeR;
      if (torsoRef.current) {
        torsoRef.current.rotation.x = 0.06;
        torsoRef.current.rotation.y = Math.sin(t * 0.9) * 0.05;
      }
      if (headRef.current) {
        headRef.current.rotation.set(0.06, Math.sin(t * 1.3) * 0.22, 0);
      }
    } else if (poseMode === "sit") {
      if (leftThighRef.current) leftThighRef.current.rotation.x = -1.3;
      if (rightThighRef.current) rightThighRef.current.rotation.x = -1.3;
      if (leftCalfRef.current) leftCalfRef.current.rotation.x = 1.25;
      if (rightCalfRef.current) rightCalfRef.current.rotation.x = 1.25;
      if (leftArmRef.current) {
        leftArmRef.current.rotation.x = -0.25;
        leftArmRef.current.rotation.z = 0.18;
      }
      if (rightArmRef.current) {
        rightArmRef.current.rotation.x = -0.25;
        rightArmRef.current.rotation.z = -0.18;
      }
      if (leftForeArmRef.current) leftForeArmRef.current.rotation.x = -0.45;
      if (rightForeArmRef.current) rightForeArmRef.current.rotation.x = -0.45;
      if (torsoRef.current) torsoRef.current.rotation.set(-0.06, 0, 0);
      if (headRef.current) headRef.current.rotation.set(0, Math.sin(t * 1.1) * 0.2, 0);
    } else if (poseMode === "alert") {
      if (leftThighRef.current) leftThighRef.current.rotation.x = 0;
      if (rightThighRef.current) rightThighRef.current.rotation.x = 0;
      if (leftCalfRef.current) leftCalfRef.current.rotation.x = 0;
      if (rightCalfRef.current) rightCalfRef.current.rotation.x = 0;
      if (leftArmRef.current) {
        leftArmRef.current.rotation.x = 0;
        leftArmRef.current.rotation.z = 0.18;
      }
      if (rightArmRef.current) {
        rightArmRef.current.rotation.x = -0.35;
        rightArmRef.current.rotation.z = -2.2 + Math.sin(t * 6.5) * 0.22;
      }
      if (leftForeArmRef.current) leftForeArmRef.current.rotation.x = -0.15;
      if (rightForeArmRef.current) rightForeArmRef.current.rotation.x = -0.35;
      if (torsoRef.current) torsoRef.current.rotation.set(0, 0, 0);
      if (headRef.current) headRef.current.rotation.set(-0.04, Math.sin(t * 2.2) * 0.22, 0);
    } else if (poseMode === "pingpong") {
      if (leftThighRef.current) leftThighRef.current.rotation.x = 0.14;
      if (rightThighRef.current) rightThighRef.current.rotation.x = -0.14;
      if (leftCalfRef.current) leftCalfRef.current.rotation.x = 0.18;
      if (rightCalfRef.current) rightCalfRef.current.rotation.x = 0.18;
      if (leftArmRef.current) {
        leftArmRef.current.rotation.x = -0.25;
        leftArmRef.current.rotation.z = 0.22;
      }
      if (rightArmRef.current) {
        rightArmRef.current.rotation.x = -0.55 + Math.sin(t * 7) * 0.45;
        rightArmRef.current.rotation.z = -0.28;
      }
      if (leftForeArmRef.current) leftForeArmRef.current.rotation.x = -0.35;
      if (rightForeArmRef.current) rightForeArmRef.current.rotation.x = -0.75 + Math.cos(t * 7) * 0.35;
      if (torsoRef.current) torsoRef.current.rotation.set(0.08, Math.sin(t * 3.5) * 0.15, 0);
      if (headRef.current) headRef.current.rotation.set(0.04, Math.sin(t * 3.5) * 0.16, 0);
    } else if (poseMode === "coffee") {
      const sip = Math.max(0, Math.sin(t * 1.5));
      if (leftThighRef.current) leftThighRef.current.rotation.x = 0;
      if (rightThighRef.current) rightThighRef.current.rotation.x = 0;
      if (leftCalfRef.current) leftCalfRef.current.rotation.x = 0;
      if (rightCalfRef.current) rightCalfRef.current.rotation.x = 0;
      if (leftArmRef.current) {
        leftArmRef.current.rotation.x = 0;
        leftArmRef.current.rotation.z = 0.16;
      }
      if (rightArmRef.current) {
        rightArmRef.current.rotation.x = -0.45 - sip * 0.35;
        rightArmRef.current.rotation.z = -0.14;
      }
      if (leftForeArmRef.current) leftForeArmRef.current.rotation.x = -0.15;
      if (rightForeArmRef.current) rightForeArmRef.current.rotation.x = -0.95 - sip * 0.38;
      if (torsoRef.current) torsoRef.current.rotation.set(0, Math.sin(t * 0.8) * 0.06, 0);
      if (headRef.current) headRef.current.rotation.set(-sip * 0.08, Math.sin(t * 0.9) * 0.16, 0);
    } else {
      // Relaxed natural standing
      const breath = Math.sin(t * 2.0);
      if (leftThighRef.current) leftThighRef.current.rotation.x = 0;
      if (rightThighRef.current) rightThighRef.current.rotation.x = 0;
      if (leftCalfRef.current) leftCalfRef.current.rotation.x = 0;
      if (rightCalfRef.current) rightCalfRef.current.rotation.x = 0;
      if (leftArmRef.current) {
        leftArmRef.current.rotation.x = 0;
        leftArmRef.current.rotation.z = 0.18 + breath * 0.025;
      }
      if (rightArmRef.current) {
        rightArmRef.current.rotation.x = 0;
        rightArmRef.current.rotation.z = -0.18 - breath * 0.025;
      }
      if (leftForeArmRef.current) leftForeArmRef.current.rotation.x = -0.16;
      if (rightForeArmRef.current) rightForeArmRef.current.rotation.x = -0.16;
      if (torsoRef.current) torsoRef.current.rotation.set(0, Math.sin(t * 0.65) * 0.06, 0);
      if (headRef.current) headRef.current.rotation.set(0, Math.sin(t * 0.85) * 0.18, 0);
    }
  });

  const showCoffeeProp = role === "seeder" || poseMode === "coffee";
  const showMegaphone = role === "qa" && (poseMode === "alert" || poseMode === "done");

  return (
    <group>
      <group ref={hipsRef} position={[0, 0.44, 0]}>
        {/* Left & Right Leg Pivots */}
        {[
          { thighRef: leftThighRef, calfRef: leftCalfRef, x: 0.082 },
          { thighRef: rightThighRef, calfRef: rightCalfRef, x: -0.082 },
        ].map(({ thighRef, calfRef, x }, idx) => (
          <group key={idx} ref={thighRef} position={[x, 0, 0]}>
            {/* Upper Leg */}
            <mesh position={[0, -0.09, 0]}>
              <capsuleGeometry args={[0.056, 0.09, 6, 12]} />
              <meshPhysicalMaterial
                color={palette.skirtSkinLegs ? palette.skin : palette.pants}
                roughness={0.55}
              />
            </mesh>
            {/* Calf + Shoe Pivot */}
            <group ref={calfRef} position={[0, -0.17, 0]}>
              <mesh position={[0, -0.085, 0]}>
                <capsuleGeometry
                  args={[0.046, 0.09, 6, 12]}
                />
                <meshPhysicalMaterial
                  color={palette.shorts || palette.skirtSkinLegs ? palette.skin : palette.pants}
                  roughness={0.55}
                />
              </mesh>
              {/* Chunky Pixar Sneaker / Shoe / Heel */}
              <RoundedBox
                args={[0.105, 0.07, 0.165]}
                radius={0.025}
                position={[0, -0.195, 0.024]}
              >
                <meshPhysicalMaterial color={palette.shoe} roughness={0.35} clearcoat={0.2} />
              </RoundedBox>
              <RoundedBox
                args={[0.11, 0.028, 0.172]}
                radius={0.012}
                position={[0, -0.232, 0.024]}
              >
                <meshStandardMaterial color={palette.sole} roughness={0.4} />
              </RoundedBox>
            </group>
          </group>
        ))}

        {/* Torso + Arms + Head */}
        <group ref={torsoRef}>
          <ChibiTorsoOutfit role={role} />

          {/* Left Arm & ForeArm */}
          <group ref={leftArmRef} position={[0.195, 0.31, 0]}>
            <mesh position={[0, -0.075, 0]}>
              <capsuleGeometry args={[0.048, 0.08, 6, 10]} />
              <meshPhysicalMaterial color={palette.sleeve} roughness={0.45} />
            </mesh>
            <group ref={leftForeArmRef} position={[0, -0.15, 0]}>
              <mesh position={[0, -0.065, 0]}>
                <capsuleGeometry args={[0.042, 0.065, 6, 10]} />
                <meshPhysicalMaterial
                  color={role === "asset" ? palette.skin : palette.sleeve}
                  roughness={0.45}
                />
              </mesh>
              <mesh position={[0, -0.14, 0]}>
                <sphereGeometry args={[0.046, 12, 10]} />
                <meshPhysicalMaterial color={palette.skin} roughness={0.4} />
              </mesh>
            </group>
          </group>

          {/* Right Arm & ForeArm + Contextual Props */}
          <group ref={rightArmRef} position={[-0.195, 0.31, 0]}>
            <mesh position={[0, -0.075, 0]}>
              <capsuleGeometry args={[0.048, 0.08, 6, 10]} />
              <meshPhysicalMaterial color={palette.sleeve} roughness={0.45} />
            </mesh>
            <group ref={rightForeArmRef} position={[0, -0.15, 0]}>
              <mesh position={[0, -0.065, 0]}>
                <capsuleGeometry args={[0.042, 0.065, 6, 10]} />
                <meshPhysicalMaterial
                  color={role === "asset" ? palette.skin : palette.sleeve}
                  roughness={0.45}
                />
              </mesh>
              <mesh position={[0, -0.14, 0]}>
                <sphereGeometry args={[0.046, 12, 10]} />
                <meshPhysicalMaterial color={palette.skin} roughness={0.4} />
              </mesh>

              {/* Takeaway Coffee Cup (Image 5) */}
              {showCoffeeProp && (
                <group position={[0, -0.14, 0.06]} rotation={[0.4, 0, 0]}>
                  <mesh>
                    <cylinderGeometry args={[0.042, 0.032, 0.11, 14]} />
                    <meshStandardMaterial color="#f8fafc" roughness={0.3} />
                  </mesh>
                  <mesh position={[0, -0.005, 0]}>
                    <cylinderGeometry args={[0.043, 0.036, 0.05, 14]} />
                    <meshStandardMaterial color="#92400e" roughness={0.7} />
                  </mesh>
                  <mesh position={[0, 0.062, 0]}>
                    <cylinderGeometry args={[0.045, 0.045, 0.018, 14]} />
                    <meshStandardMaterial color="#18181b" />
                  </mesh>
                  <mesh position={[0.012, 0.085, 0]}>
                    <cylinderGeometry args={[0.004, 0.004, 0.05, 6]} />
                    <meshStandardMaterial color="#18181b" />
                  </mesh>
                </group>
              )}

              {/* Cyan Megaphone (Image 3) */}
              {showMegaphone && (
                <group position={[0, -0.14, 0.08]} rotation={[Math.PI / 2, 0, 0]}>
                  <mesh>
                    <cylinderGeometry args={[0.075, 0.028, 0.15, 16]} />
                    <meshPhysicalMaterial color="#2dd4bf" roughness={0.25} clearcoat={0.4} />
                  </mesh>
                </group>
              )}
            </group>
          </group>

          {/* Neck */}
          <mesh position={[0, 0.37, 0]}>
            <cylinderGeometry args={[0.055, 0.065, 0.09, 12]} />
            <meshPhysicalMaterial color={palette.skin} roughness={0.4} />
          </mesh>

          {/* Big Sculpted Pixar-Chibi Head */}
          <group ref={headRef} position={[0, 0.64, 0]}>
            <mesh geometry={headGeom}>
              <meshPhysicalMaterial
                color={palette.skin}
                roughness={0.38}
                clearcoat={0.16}
                sheen={0.3}
                sheenColor="#ffe4e6"
              />
            </mesh>
            {/* Cute Ears */}
            {[-0.27, 0.27].map((ex, i) => (
              <mesh key={i} position={[ex, -0.02, -0.01]} scale={[0.7, 1.0, 0.7]}>
                <sphereGeometry args={[0.055, 12, 10]} />
                <meshPhysicalMaterial color={palette.skin} roughness={0.4} />
              </mesh>
            ))}

            <ChibiEyesAndFace
              irisColor={palette.iris}
              coolPout={palette.pout}
              hasEyelashes={palette.lashes}
            />
            <ChibiHairAndHeadwear role={role} />
          </group>
        </group>
      </group>
    </group>
  );
}
