import os
import sys
import subprocess
from datetime import datetime
import time

# 获取当前脚本所在目录
script_dir = os.path.dirname(os.path.abspath(__file__))

# 注册自定义模板过滤器
def format_time(timestamp_str):
    try:
        dt = datetime.fromisoformat(timestamp_str)
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    except:
        return '未知时间'

# 当前时间
def now():
    return datetime.now().isoformat()
    
# 计算时间差
def get_time_diff(timestamp_str, current_time_str):
    try:
        dt1 = datetime.fromisoformat(timestamp_str)
        dt2 = datetime.fromisoformat(current_time_str)
        diff_seconds = (dt2 - dt1).total_seconds()
        return int(diff_seconds)
    except:
        return 9999

# 格式化时间差
def format_time_ago(seconds):
    if seconds < 60:
        return f"{seconds}秒前"
    elif seconds < 3600:
        return f"{seconds//60}分钟前"
    elif seconds < 86400:
        return f"{seconds//3600}小时前"
    else:
        return f"{seconds//86400}天前"

def main():
    # 确保当前目录是服务器脚本所在目录
    os.chdir(script_dir)
    
    # 导入Flask应用
    sys.path.insert(0, script_dir)
    from server import app
    
    # 注册自定义模板过滤器
    app.jinja_env.filters['format_time'] = format_time
    
    # 注册上下文处理器
    @app.context_processor
    def utility_processor():
        return dict(
            now=now, 
            get_time_diff=get_time_diff, 
            format_time=format_time,
            format_time_ago=format_time_ago
        )
    
    # 服务器配置
    host = "0.0.0.0"
    port = 5000
    debug = True
    
    print(f"启动服务器...")
    print(f"监听地址: {host}:{port}")
    print(f"调试模式: {'开启' if debug else '关闭'}")
    
    # 运行Flask应用
    app.run(host=host, port=port, debug=debug)

if __name__ == "__main__":
    main() 