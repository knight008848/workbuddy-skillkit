# 发布到技能市场

## 前置检查

发布前必须过三关，任何一关不过都会被驳回：

```bash
python build/pack.py check skills/<name>      # 字段与目录白名单
python build/pack.py pack  skills/<name>      # 产物在 build/out/
```

1. **`author` 换成入驻主体名** —— 当前两个技能都还是占位符「个人开发者」。
   `check` 只提醒，`pack` 会直接中止，除非显式加 `--allow-placeholder`（仅限本地试打包）。
2. **版本号已递增**，且 `CHANGELOG.md` 顶部条目与之一致。
3. **在自己机器上真跑过一遍**，不是只看代码。

## 上架七步

| 步骤 | 做什么 | 注意 |
|---|---|---|
| 1 | 注册入驻 | 主体名就是要填进 `author` 的那个名字 |
| 2 | 资质认证 | 认证通过前提交会被退回 |
| 3 | 创建应用，业务类型选「技能」 | 选错类型要重新走一遍 |
| 4 | 上传 zip | 用 `build/out/<name>-<version>.zip`，不要手动压缩 |
| 5 | 提交审核 | 更新说明从 `CHANGELOG.md` 对应条目改写 |
| 6 | 发布上线 | 通过后才会对外可见 |
| 7 | 版本维护 | 后续更新重复 4–6 步 |

报错或流程卡住：`openworkbuddy@tencent.com`

## 驳回常见原因

| 现象 | 原因 | 怎么修 |
|---|---|---|
| 提示缺少字段 | frontmatter 少字段或值写成空串 | `pack.py check` 直接列出来 |
| 目录不合规 | 出现 `assets/`、`examples/` 等白名单外的目录 | 移动到 `templates/` 或 `references/` 下 |
| 上传后解压异常 | 手动右键压缩，多套了一层文件夹 | 只用 `pack.py pack`，它固定以 `<name>/` 为根目录 |
| 技能名对不上 | `name` 字段与目录名不一致 | 改成一致，`check` 会核对 |
| 技能装了没反应 | zip 里没有 `SKILL.md`，或不在根目录 | 同上，用 `pack.py` |

## 版本与审核的对应关系

每次提交审核都对应一个 tag，方便回溯「线上那版到底是哪份代码」：

```bash
git tag                              # 看已发布版本
git show bilingual-subtitle-v1.1.0   # 看那一版改了什么
```

写更新说明时，直接取对应 tag 的 `CHANGELOG.md` 条目，不要凭印象描述。
