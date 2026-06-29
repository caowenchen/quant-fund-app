import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from database import init_db
from main import app
from scheduler import FundScheduler
from config import Config


def main():
    print("=" * 60)
    print("  量化基金交易系统 v1.0")
    print("=" * 60)

    init_db()
    print("[Main] 数据库初始化完成")

    scheduler = FundScheduler()
    scheduler.start()

    print(f"\n[Main] API服务启动: http://{Config.HOST}:{Config.PORT}")
    print("[Main] 按 Ctrl+C 停止服务\n")

    try:
        app.run(host=Config.HOST, port=Config.PORT, debug=Config.DEBUG, use_reloader=False)
    except KeyboardInterrupt:
        print("\n[Main] 正在停止服务...")
    finally:
        scheduler.stop()
        print("[Main] 服务已停止")


if __name__ == "__main__":
    main()
