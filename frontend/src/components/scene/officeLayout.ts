import type { AgentLocation, AgentRole, AgentVisualStatus } from "../../types";

export type CoreRole = "leader" | "asset" | "dev" | "qa";

export const CORE_ROLES: CoreRole[] = ["leader", "asset", "dev", "qa"];

export type HairStyle =
  | "swept"
  | "fade"
  | "bun"
  | "spiky"
  | "ponytail"
  | "short"
  | "parted";

export type AccessoryType =
  | "crown"
  | "headset"
  | "beret"
  | "headphones"
  | "glasses"
  | "watch"
  | "visor";

export type RoomKey = "leader_room" | "staff_room" | "lounge_room";

export interface DeskSpec {
  role: AgentRole;
  label: string;
  department: string;
  homeRoom: RoomKey;
  shirtColor: string;
  hairColor: string;
  skinColor: string;
  hairstyle: HairStyle;
  accessory: AccessoryType;
  deskPos: [number, number, number];
  standPos: [number, number, number];
  deskRotationY: number;
  heightScale: number;
}

export const HALLWAY_Z = 0.45;

export const ROOM_DOORS: Record<RoomKey, [number, number, number]> = {
  leader_room: [-6.0, 0, -0.7],
  staff_room: [3.6, 0, -0.7],
  lounge_room: [0, 0, 1.6],
};

export const HOME_ROOM_BY_ROLE: Record<AgentRole, RoomKey> = {
  leader: "leader_room",
  asset: "staff_room",
  dev: "staff_room",
  qa: "staff_room",
  config: "staff_room",
  ui_dev_1: "staff_room",
  ui_dev_2: "staff_room",
  seeder: "staff_room",
};

export const BUG_BOARD_POS: [number, number, number] = [9.7, 1.68, -2.3];
export const BUG_BOARD_STAND_SPOT: [number, number, number] = [8.45, 0, -2.3];

const ASSET_LOUNGE_SPOT = {
  pos: [0.8, 0, 2.62] as [number, number, number],
  rotY: 0,
  activity: "🛋️ Nghỉ ngơi trên Sofa giải trí",
};

const DEV_LOUNGE_SPOT = {
  pos: [-3.8, 0, 3.05] as [number, number, number],
  rotY: 0.25,
  activity: "🧋 Uống trà thư giãn tại phòng giải trí",
};

export const LOUNGE_SPOTS: Record<
  AgentRole,
  { pos: [number, number, number]; rotY: number; activity: string }
> = {
  leader: {
    pos: [-5.6, 0, 2.95],
    rotY: 0.2,
    activity: "☕ Uống Espresso tại quầy bar",
  },
  asset: ASSET_LOUNGE_SPOT,
  config: ASSET_LOUNGE_SPOT,
  seeder: ASSET_LOUNGE_SPOT,
  dev: DEV_LOUNGE_SPOT,
  ui_dev_1: DEV_LOUNGE_SPOT,
  ui_dev_2: DEV_LOUNGE_SPOT,
  qa: {
    pos: [5.0, 0, 3.85],
    rotY: Math.PI / 2,
    activity: "🏓 Đánh bóng bàn giải trí",
  },
};

const ASSET_IDLE_BUBBLES = [
  "🖼️ Sẵn sàng nén WebP & Font",
  "⚙️ Kiểm tra cấu hình source & seed",
];

const DEV_IDLE_BUBBLES = [
  "💻 Sẵn sàng code HTML, CSS & Responsive",
  "✨ Chuẩn hóa tokens & layout Nasanic",
];

export const IDLE_WORK_BUBBLES: Record<AgentRole, string[]> = {
  leader: [
    "📐 Rà soát kiến trúc hệ thống",
    "📊 Chuẩn bị giao việc cho team",
  ],
  asset: ASSET_IDLE_BUBBLES,
  config: ASSET_IDLE_BUBBLES,
  seeder: ASSET_IDLE_BUBBLES,
  dev: DEV_IDLE_BUBBLES,
  ui_dev_1: DEV_IDLE_BUBBLES,
  ui_dev_2: DEV_IDLE_BUBBLES,
  qa: [
    "🧪 Sẵn sàng Playwright 3 viewports",
    "🔍 Kiểm tra quy chuẩn CSS & responsive",
  ],
};

export interface CameraZone {
  id: string;
  label: string;
  target: [number, number, number];
  position: [number, number, number];
}

export const CAMERA_ZONES: CameraZone[] = [
  {
    id: "overview",
    label: "🏢 Toàn cảnh",
    target: [0, 0.4, 0],
    position: [0, 12.2, 14.2],
  },
  {
    id: "leader_room",
    label: "👑 Phòng Leader",
    target: [-6.0, 0.7, -3.3],
    position: [-6.0, 6.2, 2.6],
  },
  {
    id: "staff_room",
    label: "💻 Phòng Nhân viên",
    target: [3.4, 0.7, -3.3],
    position: [3.4, 6.8, 3.4],
  },
  {
    id: "lounge_room",
    label: "🎮 Phòng Giải trí",
    target: [0, 0.7, 3.6],
    position: [0, 7.2, 11.4],
  },
];

function makeDeskLayout(x: number, z: number, rotY: number): {
  deskPos: [number, number, number];
  standPos: [number, number, number];
  deskRotationY: number;
} {
  return {
    deskPos: [x, 0, z],
    standPos: [
      Number((x - 0.66 * Math.sin(rotY)).toFixed(3)),
      0,
      Number((z - 0.66 * Math.cos(rotY)).toFixed(3)),
    ],
    deskRotationY: rotY,
  };
}

const ASSET_DESK_BASE = {
  label: "Linh (Assets & Config)",
  department: "Phòng Nhân viên",
  homeRoom: "staff_room" as RoomKey,
  shirtColor: "#fffbeb",
  hairColor: "#2e190e",
  skinColor: "#f8d5b4",
  hairstyle: "bun" as HairStyle,
  accessory: "beret" as AccessoryType,
  ...makeDeskLayout(-0.3, -3.7, 0.15),
  heightScale: 0.96,
};

const DEV_DESK_BASE = {
  label: "Vy (UI & Frontend)",
  department: "Phòng Nhân viên",
  homeRoom: "staff_room" as RoomKey,
  shirtColor: "#f43f5e",
  hairColor: "#26150c",
  skinColor: "#f8d5b4",
  hairstyle: "ponytail" as HairStyle,
  accessory: "glasses" as AccessoryType,
  ...makeDeskLayout(3.4, -3.7, 0.0),
  heightScale: 0.95,
};

export const DESK_LAYOUT: Record<AgentRole, DeskSpec> = {
  leader: {
    role: "leader",
    label: "Minh (Leader)",
    department: "Phòng Leader",
    homeRoom: "leader_room",
    shirtColor: "#ffffff",
    hairColor: "#18181b",
    skinColor: "#f6cfa9",
    hairstyle: "swept",
    accessory: "crown",
    ...makeDeskLayout(-6.2, -3.7, 0.18),
    heightScale: 1.02,
  },
  asset: { role: "asset", ...ASSET_DESK_BASE },
  config: { role: "config", ...ASSET_DESK_BASE },
  seeder: { role: "seeder", ...ASSET_DESK_BASE },
  dev: { role: "dev", ...DEV_DESK_BASE },
  ui_dev_1: { role: "ui_dev_1", ...DEV_DESK_BASE },
  ui_dev_2: { role: "ui_dev_2", ...DEV_DESK_BASE },
  qa: {
    role: "qa",
    label: "Tuấn (QA & Tester)",
    department: "Phòng Nhân viên",
    homeRoom: "staff_room",
    shirtColor: "#38bdf8",
    hairColor: "#0f172a",
    skinColor: "#f5cba7",
    hairstyle: "fade",
    accessory: "glasses",
    ...makeDeskLayout(7.0, -3.7, -0.18),
    heightScale: 1.01,
  },
};

export function getDestinationForLocation(
  role: AgentRole,
  location: AgentLocation,
  isBreakTime: boolean
): [number, number, number] {
  if (isBreakTime || location === "lounge") {
    return LOUNGE_SPOTS[role].pos;
  }
  if (location === "leader_desk") {
    if (role === "leader") {
      return DESK_LAYOUT.leader.standPos;
    }
    if (role === "asset" || role === "config" || role === "seeder") {
      return [-5.5, 0, -2.35];
    }
    if (role === "qa") {
      return [-6.9, 0, -2.35];
    }
    return [-6.2, 0, -2.35];
  }
  if (location === "bug_board") {
    const zOffset = role === "qa" ? 0 : role === "asset" ? 0.65 : -0.65;
    return [BUG_BOARD_STAND_SPOT[0], 0, BUG_BOARD_STAND_SPOT[2] + zOffset];
  }
  return DESK_LAYOUT[role].standPos;
}

export function getTargetRoom(
  role: AgentRole,
  location: AgentLocation,
  isBreakTime: boolean
): RoomKey {
  if (isBreakTime || location === "lounge") return "lounge_room";
  if (location === "leader_desk") return "leader_room";
  if (location === "bug_board") return "staff_room";
  return HOME_ROOM_BY_ROLE[role];
}

export function computeRoomToRoomWaypoints(
  fromRoom: RoomKey,
  toRoom: RoomKey,
  destPos: [number, number, number]
): Array<[number, number, number]> {
  if (fromRoom === toRoom) {
    return [destPos];
  }
  const originDoor = ROOM_DOORS[fromRoom];
  const targetDoor = ROOM_DOORS[toRoom];
  return [
    originDoor,
    [originDoor[0], 0, HALLWAY_Z],
    [targetDoor[0], 0, HALLWAY_Z],
    targetDoor,
    destPos,
  ];
}

export function computeWaypoints(
  role: AgentRole,
  location: AgentLocation,
  isBreakTime = false
): Array<[number, number, number]> {
  const dest = getDestinationForLocation(role, location, isBreakTime);
  const homeRoom = HOME_ROOM_BY_ROLE[role];
  const targetRoom = getTargetRoom(role, location, isBreakTime);
  return computeRoomToRoomWaypoints(homeRoom, targetRoom, dest);
}

export function getStatusColor(status: AgentVisualStatus): string {
  switch (status) {
    case "working_ai":
      return "#2563eb";
    case "working_offline":
      return "#059669";
    case "walking":
    case "meeting_leader":
      return "#0284c7";
    case "waiting_review":
      return "#d97706";
    case "blocked":
      return "#dc2626";
    case "done":
      return "#0d9488";
    default:
      return "#64748b";
  }
}
