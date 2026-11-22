import { VRM, VRMLoaderPlugin, VRMUtils } from "@pixiv/three-vrm";
import { useFrame } from "@react-three/fiber";
import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import type { AgentRole } from "../../types";

export type VrmPoseMode =
  | "walk"
  | "work"
  | "sit"
  | "coffee"
  | "pingpong"
  | "alert"
  | "done"
  | "stand";

interface VrmAvatarProps {
  modelPath: string;
  role: AgentRole;
  poseMode: VrmPoseMode;
  isMoving: boolean;
}

export function VrmAvatar({ modelPath, poseMode, isMoving }: VrmAvatarProps) {
  const [vrm, setVrm] = useState<VRM | null>(null);
  const offsetGroupRef = useRef<THREE.Group>(null);
  const baseHipYRef = useRef<number>(0.9);

  useEffect(() => {
    let disposed = false;
    const loader = new GLTFLoader();
    loader.register((parser) => new VRMLoaderPlugin(parser));

    loader.load(
      modelPath,
      (gltf) => {
        const loadedVrm = gltf.userData.vrm as VRM | undefined;
        if (!loadedVrm || disposed) {
          if (loadedVrm) VRMUtils.deepDispose(loadedVrm.scene);
          return;
        }

        // Rotate VRM 0.x models to face +Z (VRM 1.0 already faces +Z)
        if (loadedVrm.meta?.metaVersion === "0") {
          VRMUtils.rotateVRM0(loadedVrm);
        }

        loadedVrm.scene.traverse((obj) => {
          const mesh = obj as THREE.Mesh;
          if (mesh.isMesh) {
            mesh.castShadow = false;
            mesh.receiveShadow = false;
            mesh.frustumCulled = false;
          }
        });

        const hips = loadedVrm.humanoid.getNormalizedBoneNode("hips");
        if (hips) {
          baseHipYRef.current = hips.position.y || 0.9;
        }
        setVrm(loadedVrm);
      },
      undefined,
      () => {
        // Fallback handled by null state
      }
    );

    return () => {
      disposed = true;
      setVrm((prev) => {
        if (prev) VRMUtils.deepDispose(prev.scene);
        return null;
      });
    };
  }, [modelPath]);

  useFrame((state, delta) => {
    if (!vrm) return;

    const t = state.clock.elapsedTime;
    const h = vrm.humanoid;

    const hips = h.getNormalizedBoneNode("hips");
    const spine = h.getNormalizedBoneNode("spine");
    const head = h.getNormalizedBoneNode("head");
    const lArm = h.getNormalizedBoneNode("leftUpperArm");
    const rArm = h.getNormalizedBoneNode("rightUpperArm");
    const lFore = h.getNormalizedBoneNode("leftLowerArm");
    const rFore = h.getNormalizedBoneNode("rightLowerArm");
    const lUpLeg = h.getNormalizedBoneNode("leftUpperLeg");
    const rUpLeg = h.getNormalizedBoneNode("rightUpperLeg");
    const lLeg = h.getNormalizedBoneNode("leftLowerLeg");
    const rLeg = h.getNormalizedBoneNode("rightLowerLeg");

    const isSeated = !isMoving && (poseMode === "work" || poseMode === "sit");

    if (offsetGroupRef.current) {
      const targetY = isSeated ? -0.38 : 0;
      offsetGroupRef.current.position.y = THREE.MathUtils.lerp(
        offsetGroupRef.current.position.y,
        targetY,
        0.22
      );
    }

    if (isMoving || poseMode === "walk") {
      const stride = Math.sin(t * 9.5);
      const kneeL = Math.max(0, -Math.cos(t * 9.5)) * 0.65;
      const kneeR = Math.max(0, Math.cos(t * 9.5)) * 0.65;
      if (lUpLeg) lUpLeg.rotation.set(-stride * 0.45, 0, 0);
      if (rUpLeg) rUpLeg.rotation.set(stride * 0.45, 0, 0);
      if (lLeg) lLeg.rotation.set(kneeL, 0, 0);
      if (rLeg) rLeg.rotation.set(kneeR, 0, 0);
      if (lArm) lArm.rotation.set(0, stride * 0.35, -1.28);
      if (rArm) rArm.rotation.set(0, stride * 0.35, 1.28);
      if (lFore) lFore.rotation.set(0, -0.25, 0);
      if (rFore) rFore.rotation.set(0, 0.25, 0);
      if (spine) spine.rotation.set(0.04, stride * 0.05, 0);
      if (head) head.rotation.set(0, 0, 0);
    } else if (poseMode === "work") {
      // Seated in chair typing on keyboard above desk
      const typeL = Math.sin(t * 14) * 0.14;
      const typeR = Math.cos(t * 14) * 0.14;
      if (lUpLeg) lUpLeg.rotation.set(-1.45, 0, 0.04);
      if (rUpLeg) rUpLeg.rotation.set(-1.45, 0, -0.04);
      if (lLeg) lLeg.rotation.set(1.45, 0, 0);
      if (rLeg) rLeg.rotation.set(1.45, 0, 0);
      if (lArm) lArm.rotation.set(0, -0.82, -1.06);
      if (rArm) rArm.rotation.set(0, 0.82, 1.06);
      if (lFore) lFore.rotation.set(-0.2 + typeL, -0.58, 0);
      if (rFore) rFore.rotation.set(-0.2 + typeR, 0.58, 0);
      if (spine) spine.rotation.set(0.08, Math.sin(t * 0.8) * 0.03, 0);
      if (head) head.rotation.set(0.08, Math.sin(t * 1.1) * 0.16, 0);
    } else if (poseMode === "sit") {
      if (lUpLeg) lUpLeg.rotation.set(-1.35, 0, 0.05);
      if (rUpLeg) rUpLeg.rotation.set(-1.35, 0, -0.05);
      if (lLeg) lLeg.rotation.set(1.3, 0, 0);
      if (rLeg) rLeg.rotation.set(1.3, 0, 0);
      if (lArm) lArm.rotation.set(0, -0.2, -1.26);
      if (rArm) rArm.rotation.set(0, 0.2, 1.26);
      if (lFore) lFore.rotation.set(0, -0.35, 0);
      if (rFore) rFore.rotation.set(0, 0.35, 0);
      if (spine) spine.rotation.set(-0.04, 0, 0);
      if (head) head.rotation.set(0, Math.sin(t * 1.0) * 0.16, 0);
    } else if (poseMode === "alert") {
      if (lUpLeg) lUpLeg.rotation.set(0, 0, 0);
      if (rUpLeg) rUpLeg.rotation.set(0, 0, 0);
      if (lLeg) lLeg.rotation.set(0, 0, 0);
      if (rLeg) rLeg.rotation.set(0, 0, 0);
      if (lArm) lArm.rotation.set(0, 0, -1.32);
      if (rArm) rArm.rotation.set(0, 0.25, -0.35 + Math.sin(t * 6.5) * 0.22);
      if (lFore) lFore.rotation.set(0, -0.15, 0);
      if (rFore) rFore.rotation.set(0, 0.45, 0);
      if (spine) spine.rotation.set(0, 0, 0);
      if (head) head.rotation.set(-0.04, Math.sin(t * 2.2) * 0.18, 0);
    } else if (poseMode === "coffee") {
      const sip = Math.max(0, Math.sin(t * 1.4));
      if (lUpLeg) lUpLeg.rotation.set(0, 0, 0);
      if (rUpLeg) rUpLeg.rotation.set(0, 0, 0);
      if (lLeg) lLeg.rotation.set(0, 0, 0);
      if (rLeg) rLeg.rotation.set(0, 0, 0);
      if (lArm) lArm.rotation.set(0, 0, -1.32);
      if (rArm) rArm.rotation.set(0, 0.55 + sip * 0.2, 1.12);
      if (lFore) lFore.rotation.set(0, -0.15, 0);
      if (rFore) rFore.rotation.set(0, 0.95 + sip * 0.35, 0);
      if (spine) spine.rotation.set(0, Math.sin(t * 0.8) * 0.05, 0);
      if (head) head.rotation.set(-sip * 0.06, Math.sin(t * 0.9) * 0.14, 0);
    } else {
      const breath = Math.sin(t * 2.0);
      if (hips) hips.position.y = baseHipYRef.current + breath * 0.008;
      if (lUpLeg) lUpLeg.rotation.set(0, 0, 0);
      if (rUpLeg) rUpLeg.rotation.set(0, 0, 0);
      if (lLeg) lLeg.rotation.set(0, 0, 0);
      if (rLeg) rLeg.rotation.set(0, 0, 0);
      if (lArm) lArm.rotation.set(0, 0, -1.32 + breath * 0.02);
      if (rArm) rArm.rotation.set(0, 0, 1.32 - breath * 0.02);
      if (lFore) lFore.rotation.set(0, -0.15, 0);
      if (rFore) rFore.rotation.set(0, 0.15, 0);
      if (spine) spine.rotation.set(0, Math.sin(t * 0.65) * 0.05, 0);
      if (head) head.rotation.set(0, Math.sin(t * 0.85) * 0.14, 0);
    }

    // Natural eye blinking every ~3.5s
    if (vrm.expressionManager) {
      const blinkCycle = t % 3.6;
      const blinkVal = blinkCycle < 0.12 ? Math.sin((blinkCycle / 0.12) * Math.PI) : 0;
      vrm.expressionManager.setValue("blink", blinkVal);
    }

    vrm.update(Math.min(delta, 0.05));
  });

  if (!vrm) {
    return (
      <mesh position={[0, 0.85, 0]}>
        <capsuleGeometry args={[0.2, 0.85, 6, 12]} />
        <meshStandardMaterial color="#10b981" transparent opacity={0.5} />
      </mesh>
    );
  }

  return (
    <group ref={offsetGroupRef}>
      <primitive object={vrm.scene} />
    </group>
  );
}
