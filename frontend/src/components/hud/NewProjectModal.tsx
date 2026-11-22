import { FileText, Sparkles, Upload, X } from "lucide-react";
import { useRef, useState } from "react";
import { useOfficeStore } from "../../store/officeStore";

const PRESET_SPEC = `- Landing page doanh nghiệp Nội thất & Kiến trúc Nasanic Studio.
- Các section bắt buộc: Header cố định, Hero Banner kèm 2 nút CTA, Danh mục 3 gói dịch vụ nổi bật, Giới thiệu uy tín & checklist cam kết, Footer kèm Form đăng ký tư vấn.
- Yêu cầu kỹ thuật: Tuân thủ CSS Nasanic (không dùng aspect-ratio), responsive chuẩn Desktop 1440 / Tablet 768 / Mobile 375, hình ảnh tối ưu WebP.`;

export function NewProjectModal() {
  const show = useOfficeStore((s) => s.showNewProjectModal);
  const setShow = useOfficeStore((s) => s.setShowNewProjectModal);
  const createProject = useOfficeStore((s) => s.createProject);
  const isSubmitting = useOfficeStore((s) => s.isSubmitting);
  const lastError = useOfficeStore((s) => s.lastError);
  const health = useOfficeStore((s) => s.health);

  const [name, setName] = useState("Nasanic Landing Demo");
  const [specText, setSpecText] = useState(PRESET_SPEC);
  const [figmaUrl, setFigmaUrl] = useState(
    "https://www.figma.com/design/DEMOKEY123/Nasanic-Landing?node-id=10-101"
  );
  const [figmaToken, setFigmaToken] = useState("");
  const [targetSourceDir, setTargetSourceDir] = useState(
    health?.default_source_dir || "f:\\RBWStudio\\www\\2026_11\\source_nasani_29102026"
  );
  const [previewUrl, setPreviewUrl] = useState("");
  const [mode, setMode] = useState<"demo" | "live_sdk">("demo");
  const [enableAiVision, setEnableAiVision] = useState(false);
  const [uploadingSpec, setUploadingSpec] = useState(false);
  const [uploadNotice, setUploadNotice] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  if (!show) return null;

  const handleSpecFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploadingSpec(true);
    setUploadNotice(null);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const res = await fetch("/api/specs/parse", {
        method: "POST",
        body: formData,
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Không đọc được file đặc tả");
      }
      setSpecText(data.text || "");
      setUploadNotice(`Đã nạp đặc tả từ ${data.filename}`);
    } catch (err) {
      setUploadNotice(err instanceof Error ? err.message : "Lỗi đọc file");
    } finally {
      setUploadingSpec(false);
      e.target.value = "";
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await createProject({
      name: name.trim() || "Untitled Web Project",
      spec_text: specText.trim(),
      figma_url: figmaUrl.trim(),
      figma_token: figmaToken.trim() || undefined,
      target_source_dir: targetSourceDir.trim(),
      preview_url: previewUrl.trim() || undefined,
      mode,
      enable_ai_vision_qa: enableAiVision,
    });
  };

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 50,
        background: "rgba(2,6,23,0.72)",
        backdropFilter: "blur(6px)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 16,
      }}
    >
      <form
        onSubmit={handleSubmit}
        className="glass-panel"
        style={{
          width: "100%",
          maxWidth: 640,
          maxHeight: "90vh",
          overflowY: "auto",
          borderRadius: 16,
          padding: 22,
          display: "flex",
          flexDirection: "column",
          gap: 14,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <Sparkles size={18} color="#3b82f6" />
            <h2 style={{ margin: 0, fontSize: 17 }}>Khởi tạo dự án trong 3D Office</h2>
          </div>
          <button
            type="button"
            onClick={() => setShow(false)}
            style={{
              background: "transparent",
              border: "none",
              color: "#94a3b8",
              cursor: "pointer",
            }}
          >
            <X size={18} />
          </button>
        </div>

        <label style={{ display: "flex", flexDirection: "column", gap: 6, fontSize: 12 }}>
          <span>Tên dự án</span>
          <input
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
            style={inputStyle}
          />
        </label>

        <div style={{ display: "flex", flexDirection: "column", gap: 6, fontSize: 12 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
            <span>Đặc tả yêu cầu (Spec)</span>
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <input
                ref={fileInputRef}
                type="file"
                accept=".docx,.xlsx,.txt,.md,.csv"
                onChange={handleSpecFileChange}
                style={{ display: "none" }}
              />
              <button
                type="button"
                disabled={uploadingSpec}
                onClick={() => fileInputRef.current?.click()}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 4,
                  fontSize: 11,
                  background: "rgba(16,185,129,0.18)",
                  color: "#6ee7b7",
                  border: "1px solid rgba(16,185,129,0.4)",
                  borderRadius: 6,
                  padding: "3px 8px",
                  cursor: "pointer",
                }}
              >
                <Upload size={12} />
                {uploadingSpec ? "Đang đọc file..." : "Tải Word / Excel (.docx, .xlsx)"}
              </button>
              <button
                type="button"
                onClick={() => setSpecText(PRESET_SPEC)}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 4,
                  fontSize: 11,
                  background: "rgba(59,130,246,0.18)",
                  color: "#93c5fd",
                  border: "1px solid rgba(59,130,246,0.35)",
                  borderRadius: 6,
                  padding: "3px 8px",
                  cursor: "pointer",
                }}
              >
                <FileText size={12} />
                Nạp mẫu Nasanic
              </button>
            </div>
          </div>
          {uploadNotice && (
            <div style={{ fontSize: 11, color: "#93c5fd" }}>{uploadNotice}</div>
          )}
          <textarea
            required
            rows={4}
            value={specText}
            onChange={(e) => setSpecText(e.target.value)}
            style={{ ...inputStyle, resize: "vertical" }}
          />
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          <label style={{ display: "flex", flexDirection: "column", gap: 6, fontSize: 12 }}>
            <span>Link Figma</span>
            <input
              value={figmaUrl}
              onChange={(e) => setFigmaUrl(e.target.value)}
              placeholder="https://www.figma.com/design/..."
              style={inputStyle}
            />
          </label>
          <label style={{ display: "flex", flexDirection: "column", gap: 6, fontSize: 12 }}>
            <span>Figma Token (tuỳ chọn, không lưu ổ cứng)</span>
            <input
              type="password"
              value={figmaToken}
              onChange={(e) => setFigmaToken(e.target.value)}
              placeholder="figd_... (để trống nếu test Demo)"
              style={inputStyle}
            />
          </label>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          <label style={{ display: "flex", flexDirection: "column", gap: 6, fontSize: 12 }}>
            <span>Thư mục Source gốc</span>
            <input
              value={targetSourceDir}
              onChange={(e) => setTargetSourceDir(e.target.value)}
              style={inputStyle}
            />
          </label>
          <label style={{ display: "flex", flexDirection: "column", gap: 6, fontSize: 12 }}>
            <span>URL Preview (để trống = Sandbox tự động)</span>
            <input
              value={previewUrl}
              onChange={(e) => setPreviewUrl(e.target.value)}
              placeholder="http://localhost:8000 (tuỳ chọn)"
              style={inputStyle}
            />
          </label>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 8, fontSize: 12 }}>
          <span>Chế độ vận hành</span>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
            <button
              type="button"
              onClick={() => setMode("demo")}
              style={{
                textAlign: "left",
                padding: 10,
                borderRadius: 10,
                cursor: "pointer",
                background: mode === "demo" ? "rgba(16,185,129,0.18)" : "rgba(15,23,42,0.8)",
                border:
                  mode === "demo"
                    ? "1px solid #10b981"
                    : "1px solid rgba(148,163,184,0.25)",
                color: "#f1f5f9",
              }}
            >
              <div style={{ fontWeight: 700, fontSize: 12 }}>Demo (0 Token + Playwright thật)</div>
              <div style={{ fontSize: 11, color: "#94a3b8", marginTop: 3 }}>
                Chạy thật Asset WebP, Font, HTML/CSS và Chromium QA bắt lỗi để duyệt.
              </div>
            </button>

            <button
              type="button"
              onClick={() => setMode("live_sdk")}
              style={{
                textAlign: "left",
                padding: 10,
                borderRadius: 10,
                cursor: "pointer",
                background: mode === "live_sdk" ? "rgba(59,130,246,0.2)" : "rgba(15,23,42,0.8)",
                border:
                  mode === "live_sdk"
                    ? "1px solid #3b82f6"
                    : "1px solid rgba(148,163,184,0.25)",
                color: "#f1f5f9",
              }}
            >
              <div style={{ fontWeight: 700, fontSize: 12 }}>
                Live Antigravity SDK {health?.sdk.available ? "(Sẵn sàng)" : "(Chưa auth)"}
              </div>
              <div style={{ fontSize: 11, color: "#94a3b8", marginTop: 3 }}>
                Gọi thật google-antigravity SDK nạp rules từ .agents/ + Offline QA.
              </div>
            </button>
          </div>
        </div>

        <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12, color: "#cbd5e1" }}>
          <input
            type="checkbox"
            checked={enableAiVision}
            onChange={(e) => setEnableAiVision(e.target.checked)}
          />
          <span>Bật AI Vision QA ở bước cuối (mặc định tắt để tiết kiệm token)</span>
        </label>

        {lastError && (
          <div
            style={{
              padding: "8px 10px",
              borderRadius: 8,
              background: "rgba(239,68,68,0.16)",
              border: "1px solid rgba(239,68,68,0.45)",
              color: "#fca5a5",
              fontSize: 12,
            }}
          >
            {lastError}
          </div>
        )}

        <div style={{ display: "flex", justifyContent: "flex-end", gap: 10, marginTop: 6 }}>
          <button
            type="button"
            onClick={() => setShow(false)}
            style={{
              background: "transparent",
              border: "1px solid rgba(148,163,184,0.3)",
              color: "#cbd5e1",
              borderRadius: 8,
              padding: "8px 14px",
              cursor: "pointer",
              fontSize: 12,
            }}
          >
            Hủy
          </button>
          <button
            type="submit"
            disabled={isSubmitting}
            style={{
              background: "#2563eb",
              border: "none",
              color: "#ffffff",
              borderRadius: 8,
              padding: "8px 16px",
              fontWeight: 700,
              cursor: "pointer",
              fontSize: 12,
            }}
          >
            {isSubmitting ? "Đang giao Leader..." : "Giao việc cho Leader 🚀"}
          </button>
        </div>
      </form>
    </div>
  );
}

const inputStyle: React.CSSProperties = {
  width: "100%",
  background: "#0f172a",
  color: "#f8fafc",
  border: "1px solid rgba(148,163,184,0.3)",
  borderRadius: 8,
  padding: "8px 10px",
  fontSize: 12,
};
