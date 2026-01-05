"""
生成自签名SSL证书
用于开发环境的HTTPS支持
"""
import os
import sys
import socket
import ipaddress
from pathlib import Path
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from datetime import datetime, timedelta, timezone

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

def generate_self_signed_cert(cert_dir: Path, hostname: str = None, ip: str = None):
    """生成自签名SSL证书"""
    
    # 如果没有指定hostname，使用本地IP
    if not hostname and not ip:
        ip = get_local_ip()
    
    # 生成私钥
    print("正在生成私钥...")
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    
    # 创建证书主体名称
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "CN"),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Development"),
        x509.NameAttribute(NameOID.LOCALITY_NAME, "Development"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "QuickShare Development"),
        x509.NameAttribute(NameOID.COMMON_NAME, hostname or ip or "localhost"),
    ])
    
    # 创建证书构建器
    cert_builder = x509.CertificateBuilder()
    cert_builder = cert_builder.subject_name(subject)
    cert_builder = cert_builder.issuer_name(issuer)
    cert_builder = cert_builder.public_key(private_key.public_key())
    cert_builder = cert_builder.serial_number(x509.random_serial_number())
    cert_builder = cert_builder.not_valid_before(datetime.now(timezone.utc))
    cert_builder = cert_builder.not_valid_after(datetime.now(timezone.utc) + timedelta(days=365))
    
    # 添加扩展（包括IP和DNS名称）
    san_list = []
    if hostname:
        san_list.append(x509.DNSName(hostname))
    if ip:
        # 将IP字符串转换为 ipaddress 对象
        try:
            ip_obj = ipaddress.IPv4Address(ip)
            san_list.append(x509.IPAddress(ip_obj))
        except ValueError:
            # 如果是IPv6，尝试IPv6
            try:
                ip_obj = ipaddress.IPv6Address(ip)
                san_list.append(x509.IPAddress(ip_obj))
            except ValueError:
                print(f"警告: 无效的IP地址格式: {ip}，将跳过")
    san_list.append(x509.DNSName("localhost"))
    san_list.append(x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")))
    
    cert_builder = cert_builder.add_extension(
        x509.SubjectAlternativeName(san_list),
        critical=False,
    )
    
    # 签名证书
    print("正在签名证书...")
    certificate = cert_builder.sign(private_key, hashes.SHA256())
    
    # 保存证书
    cert_path = cert_dir / "server.crt"
    key_path = cert_dir / "server.key"
    
    print(f"正在保存证书到: {cert_path}")
    with open(cert_path, "wb") as f:
        f.write(certificate.public_bytes(serialization.Encoding.PEM))
    
    print(f"正在保存私钥到: {key_path}")
    with open(key_path, "wb") as f:
        f.write(private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ))
    
    print()
    print("=" * 60)
    print("✅ SSL证书生成成功！")
    print("=" * 60)
    print()
    print(f"证书文件: {cert_path}")
    print(f"私钥文件: {key_path}")
    print()
    print("⚠️  注意:")
    print("   - 这是自签名证书，浏览器会显示安全警告")
    print("   - 点击'高级' -> '继续访问'（不安全网站）即可")
    print("   - 仅用于开发环境，不要在生产环境使用")
    print()
    print("📋 证书包含的域名/IP:")
    if hostname:
        print(f"   - {hostname}")
    if ip:
        print(f"   - {ip}")
    print("   - localhost")
    print("   - 127.0.0.1")
    print()
    
    return cert_path, key_path

def main():
    """主函数"""
    # 获取项目根目录
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent.parent.parent
    cert_dir = project_root / "certs"
    
    print("=" * 60)
    print("  生成自签名SSL证书")
    print("=" * 60)
    print()
    
    # 创建证书目录
    cert_dir.mkdir(exist_ok=True)
    
    # 检查是否已存在证书
    cert_path = cert_dir / "server.crt"
    key_path = cert_dir / "server.key"
    
    if cert_path.exists() and key_path.exists():
        print(f"⚠️  证书文件已存在:")
        print(f"   {cert_path}")
        print(f"   {key_path}")
        print()
        response = input("是否重新生成？(Y/N，默认: N): ").strip().upper()
        if response != "Y":
            print("已取消")
            return
        print()
    
    # 获取本地IP
    local_ip = get_local_ip()
    
    # 询问是否使用IP地址
    print(f"检测到本地IP: {local_ip}")
    print()
    use_ip = input(f"是否将IP地址 ({local_ip}) 添加到证书？(Y/N，默认: Y): ").strip().upper()
    if use_ip == "" or use_ip == "Y":
        ip = local_ip
    else:
        ip = None
    
    print()
    
    # 生成证书
    try:
        generate_self_signed_cert(cert_dir, ip=ip)
    except Exception as e:
        print("=" * 60)
        print(f"❌ 证书生成失败: {e}")
        print("=" * 60)
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n已取消")
        sys.exit(1)

