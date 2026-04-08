"""
迁移脚本：将 messages 表的 id 列长度从 varchar(36) 扩展为 varchar(100)
以支持 approval-{batch_id} 格式的审批面板占位消息 id

SQLite 不支持 ALTER COLUMN，所以采用重建表的方式。
"""

import os
import sqlite3
from pathlib import Path


def migrate():
    backend_dir = Path(__file__).resolve().parents[2]
    configured = os.getenv("LUI_DB_PATH")
    if configured:
        db_path = Path(configured)
        if not db_path.is_absolute():
            db_path = backend_dir / db_path
    else:
        db_path = backend_dir / "workspace" / "lui.db"

    if not db_path.exists():
        print(f"数据库文件不存在: {db_path}")
        return

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    try:
        # 1. 检查当前 messages 表结构
        cursor.execute("PRAGMA table_info(messages)")
        columns = cursor.fetchall()
        print("当前 messages 表结构:")
        for col in columns:
            print(f"  {col}")

        # 2. 检查 id 列是否已经足够长（判断是否需要迁移）
        id_col = next((c for c in columns if c[1] == "id"), None)
        if id_col and "100" in str(id_col[2]):
            print("\n✓ id 列已经是 VARCHAR(100)，无需迁移")
            return

        print("\n开始迁移 messages.id 列...")

        # 3. 重命名旧表
        cursor.execute("ALTER TABLE messages RENAME TO messages_old")

        # 4. 创建新表（id 长度为 VARCHAR(100)）
        cursor.execute("""
            CREATE TABLE messages (
                id VARCHAR(100) NOT NULL,
                session_id VARCHAR(36) NOT NULL,
                role VARCHAR(20) NOT NULL,
                content TEXT NOT NULL,
                metadata JSON DEFAULT '{}',
                task_run_id VARCHAR(36),
                created_at DATETIME NOT NULL DEFAULT (datetime('now')),
                CONSTRAINT pk_messages PRIMARY KEY (id)
            )
        """)

        # 5. 创建原来的索引
        cursor.execute("CREATE INDEX ix_messages_session_id ON messages (session_id)")
        cursor.execute("CREATE INDEX ix_messages_task_run_id ON messages (task_run_id)")

        # 6. 迁移数据
        cursor.execute("""
            INSERT INTO messages (id, session_id, role, content, metadata, task_run_id, created_at)
            SELECT id, session_id, role, content, metadata, task_run_id, created_at
            FROM messages_old
        """)
        rows = cursor.rowcount
        print(f"  已迁移 {rows} 条消息记录")

        # 7. 删除旧表
        cursor.execute("DROP TABLE messages_old")

        conn.commit()
        print("✓ 迁移完成：messages.id 已扩展为 VARCHAR(100)")

        # 8. 验证
        cursor.execute("PRAGMA table_info(messages)")
        new_columns = cursor.fetchall()
        print("\n迁移后 messages 表结构:")
        for col in new_columns:
            print(f"  {col}")

    except Exception as e:
        conn.rollback()
        print(f"✗ 迁移失败: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    migrate()
