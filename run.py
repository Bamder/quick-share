import uvicorn
import socket

def get_local_ip():
    """获取本机内网IP"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

if __name__ == "__main__":
    local_ip = get_local_ip()
    
    print("=" * 50)
    print("🚀 文件闪传系统API服务器")
    print("=" * 50)
    print("📱 你自己访问：")
    print(f"   • http://127.0.0.1:8000 (最快)")
    print(f"   • http://localhost:8000")
    print(f"   • http://{local_ip}:8000")
    print("")
    print("👥 前端组访问：")
    print(f"   • http://{local_ip}:8000")
    print(f"   • 文档: http://{local_ip}:8000/docs")
    print(f"   • 健康检查: http://{local_ip}:8000/health")
    print("")
    print("⚠️  注意：")
    print("   • 保持电脑开机才能访问")
    print("   • 换网络后IP会变")
    print("   • 按 Ctrl+C 停止服务器")
    print("=" * 50)
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
