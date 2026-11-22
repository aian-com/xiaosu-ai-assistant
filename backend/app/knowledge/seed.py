from pathlib import Path
from app.knowledge.service import upload


def main() -> None:
    folder = Path(__file__).resolve().parents[3] / "fixtures" / "knowledge"
    if not folder.is_dir():
        raise SystemExit("未找到 fixtures/knowledge，请在本地仓库运行导入脚本")
    for path in sorted(folder.iterdir()):
        if path.is_file():
            result = upload(path.name, path.read_bytes())
            print(f"{path.name}: version={result['version_id']} deduplicated={result['deduplicated']}")
    print("示例文档已排队；索引 worker 需要后续配置 embedding 才能完成索引。")


if __name__ == "__main__":
    main()
