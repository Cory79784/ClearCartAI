# UI Recreation Spec (`/labeling`) for AI

This document is a full implementation spec to recreate the current labeling UI and behavior exactly (frontend + backend contract).

Use this as the single source of truth for another AI/codegen model.

---

## 1) Product Goal

Recreate a web labeling UI equivalent to the existing Gradio prototype:

- Upload ZIP product folders
- Load next unlabeled image
- Click image to segment product
- Reset image points/mask
- Skip unclear image and load next
- Save label (packaging + product name) and auto-load next
- Show status messages exactly as backend returns

No ML logic should be reimplemented in frontend. Frontend only orchestrates API calls and state.

---

## 2) Current Frontend Scope

Main page: `frontend/app/labeling/page.tsx`

Surrounding app shell:
- `frontend/components/TopNav.tsx`
- `frontend/app/layout.tsx`
- shared styles: `frontend/app/globals.css`

Authentication:
- cookie-based session (`credentials: include` in fetch)
- user must be logged in via `/api/auth/login`

---

## 3) Exact UI Sections and Components

Render two major cards on `/labeling`:

### A) Upload Product Folder card

Title:
- `📤 Upload Product Folder`

Description:
- "Upload a ZIP file containing one product folder with images."

Inputs:
- File input, accept `.zip`
- Text input for uploader name (optional)

Button:
- `Upload & Ingest`
- disabled when busy or no file selected

Output:
- multiline `<pre>` showing `uploadStatus`

### B) Labeling Interface card

Title:
- `🖼️ Labeling Interface`

Top controls:
- Labeler ID text input (default `anonymous`)
- Button: `Load Next Image`

Status area:
- multiline `<pre>` showing `status`

Two-column content area (responsive grid):

#### Left pane
- Sub-title: `Click on product to segment`
- Framed image container
- If `imageSrc` exists: render `<img>`
  - width: 100%
  - maxHeight: 640
  - objectFit: contain
  - cursor: crosshair
  - onClick => send scaled coordinates
- If no image: show "No image loaded."

Buttons below image:
- `Reset Image`
- `Skip (Not clear) → Next`
- both disabled when busy or no image

#### Right pane
- Sub-title: `Label Information`
- Input: Packaging Type
- Input: Product Name
- Button: `Save & Load Next` (disabled when busy or no image)
- Sub-title: `Instructions`
- Ordered list:
  1. Click Load Next Image
  2. Click on the product to segment
  3. Fill packaging and product name
  4. Click Save & Load Next

---

## 4) Frontend State Model (exact)

In React component local state:

- `labelerId: string` default `"anonymous"`
- `uploaderName: string` default `""`
- `uploadFile: File | null` default `null`
- `uploadStatus: string` default `""`
- `status: string` default `"Click Load Next Image to begin."`
- `sessionId: string | null` default `null`
- `imageSrc: string | null` default `null` (base64 data URL from backend)
- `packaging: string` default `""`
- `productName: string` default `""`
- `busy: boolean` default `false`
- `hasImage` derived from `!!imageSrc && !!sessionId`

---

## 5) Frontend Behavior Rules

1. Every API call must include cookies:
   - `credentials: "include"`

2. JSON helper:
   - POST with `Content-Type: application/json`
   - parse JSON
   - throw on non-2xx using `data.detail || "Request failed"`

3. Upload call:
   - multipart form fields:
     - `file`
     - `uploader_name`
   - endpoint: `/api/labeling/upload`
   - set `uploadStatus` from `data.status`

4. Load Next:
   - endpoint: `/api/labeling/load-next`
   - body: `{ labeler_id, session_id }`
   - update:
     - `sessionId`
     - `imageSrc`
     - `status`
     - clear packaging/productName

5. Image click coordinates:
   - must convert rendered coordinates to natural image coordinates:
     - `scaleX = naturalWidth / renderedWidth`
     - `scaleY = naturalHeight / renderedHeight`
     - `x = floor(localX * scaleX)`
     - `y = floor(localY * scaleY)`
   - endpoint: `/api/labeling/add-point`

6. Reset:
   - endpoint: `/api/labeling/reset`
   - body: `{ session_id }`

7. Skip:
   - endpoint: `/api/labeling/skip`
   - body: `{ session_id, labeler_id, reason: "not_clear" }`

8. Save:
   - endpoint: `/api/labeling/save`
   - body: `{ session_id, packaging, product_name }`
   - clear packaging/productName on success

9. Error handling:
   - prepend/assign user-readable message, keep UI stable

10. Busy state:
   - set `busy=true` before each async action
   - set `busy=false` in `finally`
   - use to disable buttons/actions

---

## 6) Backend API Contract (required for exact UI)

Base: `/api/labeling`

### `POST /upload` (multipart/form-data)
Fields:
- `file`: ZIP file
- `uploader_name`: string (optional)

Response:
```json
{ "status": "multiline string" }
```

### `POST /load-next`
Request:
```json
{ "labeler_id": "anonymous", "session_id": "optional-session-id-or-null" }
```
Response:
```json
{
  "session_id": "uuid",
  "image": "data:image/png;base64,... or null",
  "status": "multiline string"
}
```

### `POST /add-point`
Request:
```json
{ "session_id": "uuid", "x": 120, "y": 250 }
```
Response:
```json
{
  "session_id": "uuid",
  "image": "data:image/png;base64,...",
  "status": "multiline string with score"
}
```

### `POST /reset`
Request:
```json
{ "session_id": "uuid" }
```
Response:
same shape as add-point/load-next

### `POST /skip`
Request:
```json
{ "session_id": "uuid", "labeler_id": "anonymous", "reason": "not_clear" }
```
Response:
same shape as load-next

### `POST /save`
Request:
```json
{
  "session_id": "uuid",
  "packaging": "box",
  "product_name": "Milk 1L"
}
```
Response:
same shape as load-next

---

## 7) Styling / Design Tokens (must match)

Defined in `frontend/app/globals.css`:

Colors:
- `--bg: #0b1220`
- `--panel: #131c2f`
- `--panel-2: #1a2540`
- `--text: #e6edf7`
- `--muted: #9db0d0`
- `--accent: #6aa2ff`
- `--ok: #2bc48a`
- `--warn: #f6b73c`
- `--danger: #ff6a6a`

Core utility classes:
- `.shell`, `.topbar`, `.title`, `.nav`
- `.card`
- `.input`, `.button`, `.select`
- `.grid`
- `.badge`
- `.status-*`
- `.muted`
- `.iframeWrap`
- `pre` block style (wrapped multiline status)

Design style:
- dark-themed, rounded cards, gradients
- clean spacing and readable controls
- simple enterprise dashboard aesthetic

---

## 8) Navigation Expectations

Top nav currently includes:
- Dashboard
- Labeling UI
- Admin
- Logout

Do not show `Upload ZIP` and `Jobs` links in nav.

---

## 9) Performance Notes (must preserve)

Backend optimizations already present and should be kept:

1. Segmenter lazy initialization (no SAM2 init at app import)
2. Reuse image embeddings for repeated clicks on same image
3. Non-blocking warmup on load-next
4. CPU-safe autocast behavior in SAM2 wrapper
5. Labeling image resize via env:
   - `LABELING_MAX_SIZE` (default 1024)
6. Warmup toggle env:
   - `PRECOMPUTE_ON_LOAD=1|0`

---

## 10) Backend Runtime Constraints

Environment / assumptions:
- backend runs at `http://localhost:8000`
- frontend uses `API_BASE` from `frontend/lib/api.ts`
- auth cookie required for labeling endpoints
- database and files are handled by existing Python services

---

## 11) Non-Functional Constraints

- Do not rewrite ML internals
- Do not duplicate segmentation algorithm in frontend
- Keep endpoint semantics stable
- Keep request/response shape stable
- Keep status messaging human-readable and multiline

---

## 12) Recreation Checklist

Use this checklist to verify parity:

- [ ] Upload ZIP card exists and works
- [ ] Labeling interface card exists and works
- [ ] Load-next returns image + session
- [ ] Clicking image sends scaled coords and updates overlay
- [ ] Reset restores original loaded image
- [ ] Skip loads next and updates status
- [ ] Save writes label and loads next
- [ ] Packaging/product fields clear after save/load
- [ ] Busy-state disables actions
- [ ] Status output shown in `<pre>` blocks
- [ ] Styling matches dark card/grid design
- [ ] Top nav includes Dashboard, Labeling UI, Admin, Logout

---

## 13) Optional Enhancements (without changing behavior)

- Show spinner while busy
- Add click debouncing
- Add toast notifications while keeping status `<pre>`
- Add keyboard shortcuts for Save / Skip / Reset

Do not change API payloads if exact compatibility is required.
