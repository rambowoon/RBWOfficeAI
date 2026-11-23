import { CheckCircle2, ClipboardCheck, Plus, RotateCcw, Sparkles, Trash2, X } from "lucide-react";
import { useEffect, useState } from "react";
import { useOfficeStore } from "../../store/officeStore";
import type {
  PlanTaskUpdate,
  ProjectState,
  SpecCardinality,
  SpecContentType,
  SpecSectionItem,
  SpecSectionScope,
  SpecSectionSource,
} from "../../types";
import { normalizeOfficeAgents } from "../../utils/defaultAgents";

const CONTENT_TYPE_OPTIONS: Array<{ value: SpecContentType; label: string }> = [
  { value: "product", label: "Sản phẩm / Dịch vụ" },
  { value: "article_single", label: "1 bài viết đơn" },
  { value: "article_list", label: "Nhiều bài viết" },
  { value: "album", label: "Album / Thư viện ảnh" },
  { value: "video", label: "Video" },
  { value: "form", label: "Form đặt lịch / Liên hệ" },
  { value: "layout", label: "Bố cục tĩnh" },
  { value: "feature", label: "Tính năng / Cấu hình" },
];

const SCOPE_OPTIONS: Array<{ value: SpecSectionScope; label: string }> = [
  { value: "menu", label: "Mục trên Menu" },
  { value: "homepage", label: "Mục lớn Trang chủ" },
  { value: "inner_page", label: "Trang trong" },
  { value: "global", label: "Toàn trang" },
];

const SCOPE_BADGE: Record<
  SpecSectionScope,
  { label: string; bg: string; color: string; border: string }
> = {
  menu: {
    label: "Menu",
    bg: "rgba(139,92,246,0.18)",
    color: "#c4b5fd",
    border: "rgba(139,92,246,0.45)",
  },
  homepage: {
    label: "Mục lớn Trang chủ",
    bg: "rgba(14,165,233,0.16)",
    color: "#7dd3fc",
    border: "rgba(14,165,233,0.4)",
  },
  inner_page: {
    label: "Trang trong",
    bg: "rgba(100,116,139,0.2)",
    color: "#cbd5e1",
    border: "rgba(148,163,184,0.35)",
  },
  global: {
    label: "Toàn trang",
    bg: "rgba(100,116,139,0.2)",
    color: "#cbd5e1",
    border: "rgba(148,163,184,0.35)",
  },
};

const SOURCE_BADGE: Record<
  SpecSectionSource,
  { label: string; bg: string; color: string; border: string }
> = {
  figma_and_spec: {
    label: "Figma + Đặc tả",
    bg: "rgba(16,185,129,0.16)",
    color: "#34d399",
    border: "rgba(16,185,129,0.45)",
  },
  figma_only: {
    label: "Chỉ Figma",
    bg: "rgba(245,158,11,0.16)",
    color: "#fbbf24",
    border: "rgba(245,158,11,0.45)",
  },
  spec_only: {
    label: "Từ Đặc tả",
    bg: "rgba(56,189,248,0.16)",
    color: "#38bdf8",
    border: "rgba(56,189,248,0.45)",
  },
};

function inferCardinality(contentType: SpecContentType): SpecCardinality {
  if (contentType === "article_single") return "single";
  if (
    contentType === "product" ||
    contentType === "article_list" ||
    contentType === "album" ||
    contentType === "video"
  ) {
    return "multiple";
  }
  return "none";
}

function renderMarkdownFromSections(
  project: ProjectState,
  sections: SpecSectionItem[],
  globalText: string
): string {
  const ctypeMap = Object.fromEntries(CONTENT_TYPE_OPTIONS.map((o) => [o.value, o.label]));
  const scopeMap = Object.fromEntries(SCOPE_OPTIONS.map((o) => [o.value, o.label]));
  const sectionBlocks = sections.map((sec, idx) => {
    const order = idx + 1;
    const srcLabel = SOURCE_BADGE[sec.source]?.label || sec.source;
    const frameSuffix = sec.figma_section_name ? ` (Frame: \`${sec.figma_section_name}\`)` : "";
    const catLabel = sec.category_levels > 0 ? `Danh mục ${sec.category_levels} cấp` : "Không phân cấp";
    const req = sec.spec_requirements.trim() || "_Chưa có mô tả chi tiết_";
    const lines = [
      `### Mục ${order}. ${sec.name || `Mục ${order}`}`,
      `- **Nguồn đối chiếu**: ${srcLabel}${frameSuffix}`,
      `- **Phạm vi**: ${scopeMap[sec.scope] || sec.scope} | **Loại dữ liệu**: ${ctypeMap[sec.content_type] || sec.content_type} | **Cấp danh mục**: ${catLabel}`,
      `- **Yêu cầu chi tiết**: ${req}`,
    ];
    if (sec.notes.trim()) {
      lines.push(`- **Ghi chú kỹ thuật**: ${sec.notes.trim()}`);
    }
    return lines.join("\n");
  });

  const globals = globalText
    .split("\n")
    .map((l) => l.trim())
    .filter(Boolean)
    .map((l) => `- ${l}`);

  return [
    `# ĐẶC TẢ PHÂN TÍCH DỰ ÁN: ${project.name}`,
    `## 1. Framework & Nguồn thiết kế\n- Framework: \`${project.framework}\``,
    `## 2. Đặc tả chi tiết theo từng mục (Ưu tiên Figma → đối chiếu Đặc tả)\n\n${sectionBlocks.join("\n\n")}`,
    globals.length > 0
      ? `## 3. Chức năng chung & Yêu cầu kỹ thuật / SEO\n${globals.join("\n")}`
      : "",
  ]
    .filter(Boolean)
    .join("\n\n");
}

export function PlanReviewDrawer() {
  const projects = useOfficeStore((s) => s.projects);
  const activeProjectId = useOfficeStore((s) => s.activeProjectId);
  const show = useOfficeStore((s) => s.showPlanReview);
  const setShow = useOfficeStore((s) => s.setShowPlanReview);
  const approveLeaderPlan = useOfficeStore((s) => s.approveLeaderPlan);
  const isSubmitting = useOfficeStore((s) => s.isSubmitting);

  const activeProject = projects.find((p) => p.id === activeProjectId) ?? null;

  const [activeTab, setActiveTab] = useState<"sections" | "markdown">("sections");
  const [specSections, setSpecSections] = useState<SpecSectionItem[]>([]);
  const [specGlobalText, setSpecGlobalText] = useState("");
  const [planMarkdown, setPlanMarkdown] = useState("");
  const [markdownDirty, setMarkdownDirty] = useState(false);
  const [taskEdits, setTaskEdits] = useState<PlanTaskUpdate[]>([]);
  const [userNote, setUserNote] = useState("");

  useEffect(() => {
    if (!activeProject) return;
    setSpecSections(activeProject.spec_sections ?? []);
    setSpecGlobalText((activeProject.spec_global_features ?? []).join("\n"));
    setPlanMarkdown(activeProject.leader_plan_markdown ?? "");
    setMarkdownDirty(false);
    setTaskEdits(
      activeProject.tasks.map((t) => ({
        id: t.id,
        title: t.title,
        detail: t.detail ?? "",
      }))
    );
    setUserNote(activeProject.plan_review_note ?? "");
    setActiveTab(
      (activeProject.spec_sections?.length ?? 0) > 0 ? "sections" : "markdown"
    );
  }, [
    activeProject?.id,
    activeProject?.leader_plan_markdown,
    activeProject?.phase,
    activeProject?.spec_sections,
  ]);

  if (!show || !activeProject) return null;

  const isWaitingPlan = activeProject.phase === "waiting_plan_review";
  const agentsMap = normalizeOfficeAgents(activeProject.agents);
  const figmaSummary = activeProject.figma_summary as {
    file_name?: string;
    colors_count?: number;
    fonts?: string[];
    sections_count?: number;
    stats?: { compression_pct?: number; kept_node_count?: number; raw_node_count?: number };
  };
  const specMeta = activeProject.spec_metadata ?? {};

  const updateSection = (id: string, patch: Partial<SpecSectionItem>) => {
    setSpecSections((prev) =>
      prev.map((item) => {
        if (item.id !== id) return item;
        const next = { ...item, ...patch };
        if (patch.content_type) {
          next.item_cardinality = inferCardinality(patch.content_type);
        }
        return next;
      })
    );
  };

  const removeSection = (id: string) => {
    setSpecSections((prev) =>
      prev
        .filter((item) => item.id !== id)
        .map((item, idx) => ({ ...item, order: idx + 1 }))
    );
  };

  const addSection = () => {
    setSpecSections((prev) => {
      const nextOrder = prev.length + 1;
      return [
        ...prev,
        {
          id: `sec-custom-${Date.now()}`,
          order: nextOrder,
          name: `Mục mới ${nextOrder}`,
          scope: "homepage",
          source: "spec_only",
          figma_section_name: "",
          content_type: "article_list",
          category_levels: 0,
          item_cardinality: "multiple",
          spec_requirements: "",
          notes: "",
        },
      ];
    });
  };

  const handleResetDefault = () => {
    setSpecSections(activeProject.spec_sections ?? []);
    setSpecGlobalText((activeProject.spec_global_features ?? []).join("\n"));
    setPlanMarkdown(activeProject.leader_plan_markdown ?? "");
    setMarkdownDirty(false);
    setTaskEdits(
      activeProject.tasks.map((t) => ({
        id: t.id,
        title: t.title,
        detail: t.detail ?? "",
      }))
    );
  };

  const handleSyncMarkdown = () => {
    setPlanMarkdown(
      renderMarkdownFromSections(activeProject, specSections, specGlobalText)
    );
    setMarkdownDirty(false);
  };

  const handleApprove = async () => {
    if (isSubmitting) return;
    const normalizedSections = specSections.map((sec, idx) => ({
      ...sec,
      order: idx + 1,
    }));
    const globalList = specGlobalText
      .split("\n")
      .map((l) => l.trim())
      .filter(Boolean);
    const finalMarkdown =
      markdownDirty && planMarkdown.trim()
        ? planMarkdown.trim()
        : normalizedSections.length > 0
        ? renderMarkdownFromSections(activeProject, normalizedSections, specGlobalText)
        : planMarkdown.trim();
    if (!finalMarkdown && normalizedSections.length === 0) return;

    await approveLeaderPlan(activeProject.id, {
      leader_plan_markdown: finalMarkdown,
      spec_sections: normalizedSections,
      spec_global_features: globalList,
      tasks: taskEdits,
      user_note: userNote.trim(),
    });
  };

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 45,
        background: "rgba(2,6,23,0.65)",
        backdropFilter: "blur(5px)",
        display: "flex",
        justifyContent: "flex-end",
      }}
    >
      <div
        className="glass-panel"
        style={{
          width: 820,
          maxWidth: "100vw",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          borderLeft: "1px solid rgba(148,163,184,0.25)",
        }}
      >
        {/* Header */}
        <div
          style={{
            padding: "14px 18px",
            borderBottom: "1px solid rgba(148,163,184,0.2)",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 10,
          }}
        >
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
              <ClipboardCheck size={18} color="#38bdf8" />
              <strong style={{ fontSize: 16 }}>
                Đặc tả phân tích của Minh (Leader)
              </strong>
              <span
                style={{
                  fontSize: 10,
                  fontWeight: 800,
                  padding: "2px 8px",
                  borderRadius: 999,
                  background: isWaitingPlan
                    ? "rgba(245,158,11,0.2)"
                    : "rgba(16,185,129,0.2)",
                  color: isWaitingPlan ? "#fbbf24" : "#34d399",
                  border: isWaitingPlan
                    ? "1px solid rgba(245,158,11,0.5)"
                    : "1px solid rgba(16,185,129,0.45)",
                }}
              >
                {isWaitingPlan ? "Chờ bạn xem & duyệt" : "Đã duyệt & giao team"}
              </span>
            </div>
            <div style={{ fontSize: 12, color: "#94a3b8", marginTop: 3 }}>
              Dự án: <b>{activeProject.name}</b> · Framework:{" "}
              <code>{activeProject.framework}</code>
              {specSections.length > 0 && ` · ${specSections.length} mục đặc tả`}
            </div>
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
            <X size={19} />
          </button>
        </div>

        {/* Body */}
        <div
          style={{
            flex: 1,
            overflowY: "auto",
            padding: 18,
            display: "flex",
            flexDirection: "column",
            gap: 14,
          }}
        >
          {/* Figma Tokens Summary */}
          <div
            style={{
              padding: 12,
              borderRadius: 12,
              background: "rgba(15,23,42,0.75)",
              border: "1px solid rgba(56,189,248,0.28)",
              fontSize: 12,
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))",
              gap: 10,
            }}
          >
            <div>
              <div style={{ color: "#94a3b8", fontSize: 10, textTransform: "uppercase" }}>
                Figma File (Ưu tiên 1)
              </div>
              <div style={{ fontWeight: 700, color: "#f8fafc", marginTop: 2 }}>
                {figmaSummary?.file_name || "Design System"}
              </div>
            </div>
            <div>
              <div style={{ color: "#94a3b8", fontSize: 10, textTransform: "uppercase" }}>
                Nén Node Rác (0 Token)
              </div>
              <div style={{ fontWeight: 700, color: "#34d399", marginTop: 2 }}>
                {figmaSummary?.stats?.compression_pct ?? 0}% ({figmaSummary?.sections_count ?? 0}{" "}
                sections Figma)
              </div>
            </div>
            <div>
              <div style={{ color: "#94a3b8", fontSize: 10, textTransform: "uppercase" }}>
                Fonts & Màu
              </div>
              <div style={{ fontWeight: 600, color: "#cbd5e1", marginTop: 2 }}>
                {(figmaSummary?.fonts || []).join(", ") || "Be Vietnam Pro"} ·{" "}
                {figmaSummary?.colors_count ?? 0} màu
              </div>
            </div>
          </div>

          {(specMeta.contract_name || specMeta.demo_url || specMeta.package_features) && (
            <div
              style={{
                padding: "9px 12px",
                borderRadius: 10,
                background: "rgba(30,41,59,0.65)",
                border: "1px solid rgba(148,163,184,0.22)",
                fontSize: 11,
                color: "#cbd5e1",
                display: "flex",
                flexWrap: "wrap",
                gap: 12,
              }}
            >
              {specMeta.contract_name && (
                <span>
                  Hợp đồng: <strong style={{ color: "#f8fafc" }}>{specMeta.contract_name}</strong>
                </span>
              )}
              {specMeta.package_features && (
                <span>
                  Gói: <strong style={{ color: "#93c5fd" }}>{specMeta.package_features}</strong>
                </span>
              )}
              {specMeta.demo_url && (
                <span style={{ wordBreak: "break-all" }}>
                  Demo: <code style={{ color: "#6ee7b7" }}>{specMeta.demo_url}</code>
                </span>
              )}
            </div>
          )}

          {/* Tab Bar + Reset */}
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              gap: 8,
              flexWrap: "wrap",
            }}
          >
            <div style={{ display: "flex", gap: 6 }}>
              <button
                type="button"
                onClick={() => setActiveTab("sections")}
                style={tabButtonStyle(activeTab === "sections")}
              >
                Đặc tả theo từng mục ({specSections.length})
              </button>
              <button
                type="button"
                onClick={() => setActiveTab("markdown")}
                style={tabButtonStyle(activeTab === "markdown")}
              >
                Markdown tổng hợp
              </button>
            </div>
            {isWaitingPlan && (
              <button
                type="button"
                onClick={handleResetDefault}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 4,
                  fontSize: 11,
                  padding: "4px 9px",
                  borderRadius: 7,
                  background: "rgba(30,41,59,0.9)",
                  color: "#cbd5e1",
                  border: "1px solid rgba(148,163,184,0.3)",
                  cursor: "pointer",
                }}
              >
                <RotateCcw size={11} />
                <span>Khôi phục bản gốc của Leader</span>
              </button>
            )}
          </div>

          {activeTab === "sections" ? (
            <>
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                {specSections.map((sec, idx) => {
                  const badge = SOURCE_BADGE[sec.source] || SOURCE_BADGE.figma_and_spec;
                  const scopeBadge = SCOPE_BADGE[sec.scope] || SCOPE_BADGE.homepage;
                  return (
                    <div
                      key={sec.id}
                      style={{
                        padding: 12,
                        borderRadius: 11,
                        background: "rgba(15,23,42,0.82)",
                        border:
                          sec.source === "figma_only"
                            ? "1px solid rgba(245,158,11,0.45)"
                            : "1px solid rgba(148,163,184,0.24)",
                        display: "flex",
                        flexDirection: "column",
                        gap: 8,
                      }}
                    >
                      {/* Section header row */}
                      <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                        <span
                          style={{
                            fontSize: 11,
                            fontWeight: 800,
                            color: "#38bdf8",
                            minWidth: 26,
                          }}
                        >
                          #{idx + 1}
                        </span>
                        <input
                          value={sec.name}
                          readOnly={!isWaitingPlan}
                          onChange={(e) => updateSection(sec.id, { name: e.target.value })}
                          style={{
                            ...fieldStyle,
                            flex: 1,
                            minWidth: 180,
                            fontWeight: 700,
                          }}
                        />
                        <span
                          style={{
                            fontSize: 10,
                            fontWeight: 700,
                            padding: "3px 8px",
                            borderRadius: 999,
                            background: scopeBadge.bg,
                            color: scopeBadge.color,
                            border: `1px solid ${scopeBadge.border}`,
                            whiteSpace: "nowrap",
                          }}
                        >
                          {scopeBadge.label}
                        </span>
                        <span
                          style={{
                            fontSize: 10,
                            fontWeight: 700,
                            padding: "3px 8px",
                            borderRadius: 999,
                            background: badge.bg,
                            color: badge.color,
                            border: `1px solid ${badge.border}`,
                            whiteSpace: "nowrap",
                          }}
                        >
                          {badge.label}
                        </span>
                        {sec.figma_section_name && (
                          <span
                            style={{
                              fontSize: 10,
                              color: "#cbd5e1",
                              background: "rgba(30,41,59,0.9)",
                              border: "1px solid rgba(148,163,184,0.25)",
                              borderRadius: 6,
                              padding: "2px 7px",
                            }}
                          >
                            Figma: {sec.figma_section_name}
                          </span>
                        )}
                        {isWaitingPlan && (
                          <button
                            type="button"
                            title="Xóa mục này"
                            onClick={() => removeSection(sec.id)}
                            style={{
                              background: "rgba(239,68,68,0.12)",
                              border: "1px solid rgba(239,68,68,0.3)",
                              color: "#fca5a5",
                              borderRadius: 6,
                              padding: "4px 6px",
                              cursor: "pointer",
                              display: "inline-flex",
                              alignItems: "center",
                            }}
                          >
                            <Trash2 size={12} />
                          </button>
                        )}
                      </div>

                      {/* Classification dropdowns */}
                      <div
                        style={{
                          display: "grid",
                          gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))",
                          gap: 8,
                        }}
                      >
                        <label style={{ display: "flex", flexDirection: "column", gap: 3, fontSize: 10, color: "#94a3b8" }}>
                          <span>Loại dữ liệu</span>
                          <select
                            disabled={!isWaitingPlan}
                            value={sec.content_type}
                            onChange={(e) =>
                              updateSection(sec.id, {
                                content_type: e.target.value as SpecContentType,
                              })
                            }
                            style={fieldStyle}
                          >
                            {CONTENT_TYPE_OPTIONS.map((opt) => (
                              <option key={opt.value} value={opt.value}>
                                {opt.label}
                              </option>
                            ))}
                          </select>
                        </label>

                        <label style={{ display: "flex", flexDirection: "column", gap: 3, fontSize: 10, color: "#94a3b8" }}>
                          <span>Cấp danh mục</span>
                          <select
                            disabled={!isWaitingPlan}
                            value={sec.category_levels}
                            onChange={(e) =>
                              updateSection(sec.id, {
                                category_levels: Number(e.target.value),
                              })
                            }
                            style={fieldStyle}
                          >
                            <option value={0}>Không phân cấp</option>
                            <option value={1}>Danh mục 1 cấp</option>
                            <option value={2}>Danh mục 2 cấp</option>
                            <option value={3}>Danh mục 3 cấp</option>
                          </select>
                        </label>

                        <label style={{ display: "flex", flexDirection: "column", gap: 3, fontSize: 10, color: "#94a3b8" }}>
                          <span>Phạm vi</span>
                          <select
                            disabled={!isWaitingPlan}
                            value={sec.scope}
                            onChange={(e) =>
                              updateSection(sec.id, {
                                scope: e.target.value as SpecSectionScope,
                              })
                            }
                            style={fieldStyle}
                          >
                            {SCOPE_OPTIONS.map((opt) => (
                              <option key={opt.value} value={opt.value}>
                                {opt.label}
                              </option>
                            ))}
                          </select>
                        </label>
                      </div>

                      {/* Requirements + Notes */}
                      <textarea
                        rows={2}
                        readOnly={!isWaitingPlan}
                        value={sec.spec_requirements}
                        placeholder="Yêu cầu chi tiết của mục này (lấy từ Figma / file đặc tả)..."
                        onChange={(e) =>
                          updateSection(sec.id, { spec_requirements: e.target.value })
                        }
                        style={{ ...fieldStyle, resize: "vertical", fontSize: 11.5, lineHeight: 1.45 }}
                      />
                      <input
                        readOnly={!isWaitingPlan}
                        value={sec.notes}
                        placeholder="Ghi chú kỹ thuật (ẩn/hiện giá, đóng dấu logo, chạy ngang, popup, link tham khảo...)"
                        onChange={(e) => updateSection(sec.id, { notes: e.target.value })}
                        style={{ ...fieldStyle, fontSize: 11, color: "#cbd5e1" }}
                      />
                    </div>
                  );
                })}
              </div>

              {isWaitingPlan && (
                <button
                  type="button"
                  onClick={addSection}
                  style={{
                    alignSelf: "flex-start",
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 5,
                    fontSize: 11,
                    fontWeight: 700,
                    padding: "6px 11px",
                    borderRadius: 8,
                    background: "rgba(56,189,248,0.15)",
                    color: "#7dd3fc",
                    border: "1px solid rgba(56,189,248,0.35)",
                    cursor: "pointer",
                  }}
                >
                  <Plus size={13} />
                  <span>Thêm mục đặc tả</span>
                </button>
              )}

              {/* Global Features */}
              <div>
                <div style={{ fontSize: 12, fontWeight: 700, color: "#93c5fd", marginBottom: 6 }}>
                  Chức năng chung & Yêu cầu SEO / Kỹ thuật (mỗi dòng 1 yêu cầu)
                </div>
                <textarea
                  rows={4}
                  readOnly={!isWaitingPlan}
                  value={specGlobalText}
                  onChange={(e) => setSpecGlobalText(e.target.value)}
                  placeholder="Ví dụ: Icon Zalo/Mess/Hotline, Tối ưu ảnh WebP, SEO thẻ H1/H2/H3, sitemap.xml..."
                  style={{ ...fieldStyle, resize: "vertical", fontSize: 11.5, lineHeight: 1.5 }}
                />
              </div>
            </>
          ) : (
            <div>
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  marginBottom: 6,
                  gap: 8,
                }}
              >
                <span style={{ fontSize: 12, fontWeight: 700, color: "#93c5fd" }}>
                  Nội dung đặc tả Markdown (bạn có thể chỉnh sửa trực tiếp trước khi giao việc)
                </span>
                {isWaitingPlan && specSections.length > 0 && (
                  <button
                    type="button"
                    onClick={handleSyncMarkdown}
                    style={{
                      fontSize: 11,
                      padding: "4px 9px",
                      borderRadius: 7,
                      background: "rgba(56,189,248,0.16)",
                      color: "#7dd3fc",
                      border: "1px solid rgba(56,189,248,0.35)",
                      cursor: "pointer",
                    }}
                  >
                    Đồng bộ lại từ danh sách mục
                  </button>
                )}
              </div>
              <textarea
                value={planMarkdown}
                readOnly={!isWaitingPlan}
                onChange={(e) => {
                  setPlanMarkdown(e.target.value);
                  setMarkdownDirty(true);
                }}
                rows={14}
                style={{
                  width: "100%",
                  minHeight: 280,
                  background: "#0f172a",
                  color: "#f8fafc",
                  border: isWaitingPlan
                    ? "1px solid rgba(56,189,248,0.45)"
                    : "1px solid rgba(148,163,184,0.22)",
                  borderRadius: 10,
                  padding: 12,
                  fontSize: 12,
                  lineHeight: 1.55,
                  fontFamily: "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace",
                  resize: "vertical",
                }}
              />
            </div>
          )}

          {/* Editable 3-Staff Task Breakdown */}
          {taskEdits.length > 0 && (
            <div>
              <div style={{ fontSize: 12, fontWeight: 700, color: "#cbd5e1", marginBottom: 8 }}>
                Phân công dự kiến xuống 3 nhân viên (Linh → Vy → Tuấn)
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {taskEdits.map((task, idx) => {
                  const orig = activeProject.tasks[idx];
                  const assigneeName =
                    (orig && agentsMap[orig.owner_role]?.name) || orig?.owner_role || "Nhân viên";
                  return (
                    <div
                      key={task.id}
                      style={{
                        padding: 10,
                        borderRadius: 10,
                        background: "rgba(15,23,42,0.75)",
                        border: "1px solid rgba(148,163,184,0.22)",
                        display: "flex",
                        flexDirection: "column",
                        gap: 6,
                      }}
                    >
                      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11 }}>
                        <strong style={{ color: "#38bdf8" }}>
                          Bước {idx + 1}: {assigneeName}
                        </strong>
                        {orig && (
                          <span style={{ color: "#94a3b8" }}>Trạng thái: {orig.status}</span>
                        )}
                      </div>
                      <input
                        value={task.title}
                        readOnly={!isWaitingPlan}
                        onChange={(e) =>
                          setTaskEdits((prev) =>
                            prev.map((item) =>
                              item.id === task.id ? { ...item, title: e.target.value } : item
                            )
                          )
                        }
                        style={fieldStyle}
                      />
                      <input
                        value={task.detail}
                        readOnly={!isWaitingPlan}
                        placeholder="Mô tả chi tiết phạm vi đầu việc..."
                        onChange={(e) =>
                          setTaskEdits((prev) =>
                            prev.map((item) =>
                              item.id === task.id ? { ...item, detail: e.target.value } : item
                            )
                          )
                        }
                        style={{ ...fieldStyle, color: "#cbd5e1", fontSize: 11 }}
                      />
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Optional Note */}
          <div>
            <div style={{ fontSize: 12, fontWeight: 600, color: "#cbd5e1", marginBottom: 6 }}>
              Ghi chú chỉ đạo thêm cho nhân viên (tuỳ chọn)
            </div>
            <input
              value={userNote}
              readOnly={!isWaitingPlan}
              onChange={(e) => setUserNote(e.target.value)}
              placeholder="Ví dụ: Nhấn mạnh bảng giá ở Hero, ưu tiên font Be Vietnam Pro..."
              style={fieldStyle}
            />
          </div>
        </div>

        {/* Footer */}
        <div
          style={{
            padding: "12px 18px",
            borderTop: "1px solid rgba(148,163,184,0.2)",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 10,
          }}
        >
          {isWaitingPlan ? (
            <>
              <div style={{ fontSize: 11, color: "#94a3b8" }}>
                Nhân viên chỉ bắt đầu chạy sau khi bạn bấm duyệt bản đặc tả này.
              </div>
              <button
                type="button"
                disabled={isSubmitting || (!planMarkdown.trim() && specSections.length === 0)}
                onClick={handleApprove}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 6,
                  background: "#10b981",
                  border: "none",
                  color: "#0f172a",
                  borderRadius: 9,
                  padding: "9px 16px",
                  fontSize: 12,
                  fontWeight: 800,
                  cursor: isSubmitting ? "wait" : "pointer",
                  whiteSpace: "nowrap",
                }}
              >
                <Sparkles size={15} />
                <span>
                  {isSubmitting ? "Đang giao việc..." : "✅ Duyệt & Giao nhân viên làm"}
                </span>
              </button>
            </>
          ) : (
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                fontSize: 12,
                color: "#34d399",
                fontWeight: 700,
              }}
            >
              <CheckCircle2 size={16} />
              <span>Đã duyệt đặc tả — Nhân viên đang/đã triển khai theo kế hoạch này.</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function tabButtonStyle(active: boolean): React.CSSProperties {
  return {
    fontSize: 11.5,
    fontWeight: 700,
    padding: "6px 11px",
    borderRadius: 8,
    cursor: "pointer",
    background: active ? "rgba(56,189,248,0.2)" : "rgba(15,23,42,0.75)",
    color: active ? "#7dd3fc" : "#94a3b8",
    border: active
      ? "1px solid rgba(56,189,248,0.5)"
      : "1px solid rgba(148,163,184,0.22)",
  };
}

const fieldStyle: React.CSSProperties = {
  width: "100%",
  background: "#0f172a",
  color: "#f8fafc",
  border: "1px solid rgba(148,163,184,0.28)",
  borderRadius: 7,
  padding: "6px 9px",
  fontSize: 12,
};
