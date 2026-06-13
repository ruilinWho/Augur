# 「记」笔记一级文件夹（目录）

日期：2026-06-13。

作者要求把「记」做得更好，加文件夹（目录）组织。经确认：**一级文件夹**（不嵌套）、**一篇笔记归属单个文件夹**（文件系统式，非标签）。

## 数据模型

- 新表 `note_folders(id, name, sort_order, created_at)`——一级，无 parent。
- `notes.folder_id`：`INTEGER REFERENCES note_folders(id) ON DELETE SET NULL`，`NULL`=未归类。
  - **新库** SCHEMA 带 DB 级 `ON DELETE SET NULL`（删夹→笔记 `folder_id` 自动置空，不删笔记）。
  - **旧库迁移**走 `_MIGRATIONS` 的 `("notes","folder_id","INTEGER")`（普通列、不带 FK——SQLite `ALTER TABLE ADD COLUMN` 带 FK/ON DELETE 有坑），靠 service 层 `delete_folder` 显式 `UPDATE notes SET folder_id=NULL` 兜底。两条路都保证删夹不丢笔记。
  - **`idx_notes_folder` 索引放 `_migrate`（不放 SCHEMA）**——遵循 db.py 既有约定：旧库 `executescript(SCHEMA)` 时 notes 还没 `folder_id` 列，索引建在 SCHEMA 里会报错。

## 后端（`notes/`）

- service 加 `list_folders`（LEFT JOIN 带 `note_count`）/`create_folder`/`rename_folder`/`delete_folder`（先置空笔记再删夹）；`create_note` 加 `folder_id`；新增 `move_note(note_id, folder_id|None)`（校验目标夹存在）。
- router：`/notes/folders` GET/POST、`/notes/folders/{id}` PATCH/DELETE、`/notes/{id}/folder` PATCH（移动）。**`/folders` 静态路由必须在 `/{note_id}` 动态段之前声明**，否则被抢匹配（FastAPI 按声明顺序）。
- 移动用**独立端点 + `NoteMove` schema**（`folder_id: int|None`），不混进 `NotePatch`——因为 PATCH 的 `None`=「不改」，无法表达「移到未归类（设 null）」；独立端点让 null 有明确语义。

## 前端（`features/notes/`）

- `NotesNav` 用 `@dnd-kit/core`（`useDraggable` 笔记 + `useDroppable` 文件夹/未归类区，`PointerSensor` `distance:6` 区分点击/拖拽）。droppable id `folder:N`，`folder:0` = 未归类（`Number('0')||null`→null）。
- **渐进增强**：没有任何文件夹时，`NotesNav` 退化为原扁平列表（未归类区不显标题），视觉零变化；建了文件夹才出现分组 + 「未归类」拖回目标。这样没用文件夹的人体验不变（符合 foolproof / concise）。
- 文件夹**双击名字重命名**（对齐自选分区习惯）；删除 confirm「笔记会回到未归类、不删除」。hover 显「＋ 新建到此 / × 删除」，不遮挡名字。
- `api.ts` 加 `useFolders/useCreateFolder/useRenameFolder/useDeleteFolder/useMoveNote`，`noteMetaSchema/noteSchema` 加 `folder_id`，`useCreateNote` 加 `folderId`。
