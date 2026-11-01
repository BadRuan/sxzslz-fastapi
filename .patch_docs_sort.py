from pathlib import Path

readme = Path("README.md")
fa = Path("docs/frontend-api.md")

# README: 文章模块参数表插入 sort 行（在 user_id 行之后）
rtext = readme.read_text(encoding="utf-8")
old_r = """| user_id | int | 无 | 按作者用户 id 过滤（后台展示登录账户的文章） |"""
new_r = """| user_id | int | 无 | 按作者用户 id 过滤（后台展示登录账户的文章；**仅超管生效**，普通用户被强制收敛为本人） |
| sort | `id` \\| `create_at` | `id` | 排序字段（倒序）：`id`=发布 id（默认，最新创建在前）；`create_at`=发布时间（最新发布在前） |"""
assert rtext.count(old_r) == 1, f"README 未命中: {rtext.count(old_r)}"
rtext = rtext.replace(old_r, new_r)
readme.write_text(rtext, encoding="utf-8")

# frontend-api: GET /articles/ 参数表插入 sort 行
ftext = fa.read_text(encoding="utf-8")
old_fa = """| user_id | int | 无 | 按作者过滤（**仅超管生效**；普通用户被强制收敛为本人） |"""
new_fa = """| user_id | int | 无 | 按作者过滤（**仅超管生效**；普通用户被强制收敛为本人） |
| sort | `id` / `create_at` | `id` | 排序字段（倒序）：`id`=发布 id（默认，最新创建在前）；`create_at`=发布时间（最新发布在前） |"""
assert ftext.count(old_fa) == 1, f"frontend-api 未命中: {ftext.count(old_fa)}"
ftext = ftext.replace(old_fa, new_fa)

# 也在可见范围说明里加一句
old_fa2 = """| 超管 | 全量，`user_id` 过滤与 `is_deleted` 照常使用 |"""
new_fa2 = """| 超管 | 全量，`user_id` 过滤、`is_deleted` 回收站、`sort` 排序均照常使用 |"""
assert ftext.count(old_fa2) == 1, f"frontend-api 可见范围未命中"
ftext = ftext.replace(old_fa2, new_fa2)

fa.write_text(ftext, encoding="utf-8")
print("docs patched OK")
