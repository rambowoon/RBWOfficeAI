# RBWOfficeAI — Web Automation Studio

Tool nội bộ tự động biến **Đặc tả + Link Figma** thành giao diện web hoàn thiện, kết hợp:
- **3D Office Centerpiece** (React Three Fiber): Leader phân tích & giao việc, nhân viên đi lại giữa bàn làm việc / bàn Leader / Bug Board theo trạng thái thật.
- **Offline 0-Token Pipelines**:
  - Lọc Figma JSON thành `tokens.json` gọn (bỏ layer ẩn).
  - Tải/sinh font `fonts.css` & nén ảnh `.webp` bằng Pillow.
  - Kiểm tra Static Rules (cấm `aspect-ratio` Nasanic, cú pháp CSS/JS/PHP).
  - Kiểm tra thực tế bằng **Playwright Chromium** ở 3 màn hình (`1440px`, `768px`, `375px`), bắt 404, tràn ngang và chụp ảnh màn hình.
- **Bug Board (Human-in-the-loop)**: Gom toàn bộ lỗi kèm ảnh chụp cho bạn tick chọn lỗi cần sửa trước khi giao Dev fix và test lại.
- **Antigravity Python SDK (`google-antigravity`)**: Nạp trực tiếp `.agents/AGENTS.md` và `.agents/skills/*/SKILL.md` vào các AI Agent khi chạy chế độ Live SDK.

## Chạy nhanh

1. Copy `backend/.env.example` thành `backend/.env` nếu muốn cấu hình sẵn `FIGMA_ACCESS_TOKEN`.
2. Chạy script khởi động 2 cửa sổ Backend + Frontend:
   ```powershell
   .\start.ps1
   ```
3. Mở trình duyệt tại `http://127.0.0.1:5173`.
4. Chạy test backend:
   ```powershell
   cd backend
   .\.venv\Scripts\pytest -v
   ```
